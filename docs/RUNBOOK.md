# Operational Runbook & Incident Recovery

This runbook defines the v1.0.0 recovery path for the Spotify Analytics Data Platform. The
operating rule is **preserve evidence first, then replay through the normal contracts**. A
failed attempt should remain inspectable; recovery creates a new physical execution when a new
attempt is required.

The public end-to-end recovery workflow applies to the **bounded CC0-backed Airflow demo**. The
Spotify Web API + Lambda path has its own authentication and extraction recovery procedures and
must not be conflated with the CC0 replay utility.

> [!IMPORTANT]
> **Operational truth boundary:** this runbook does not assume a CloudWatch dashboard, paging
> system, or Power BI dashboard exists. It uses Airflow task state, structured failure/deadline
> events, S3 metadata, Snowflake load history, dbt artifacts, and the unified run report as the
> evidence sources that are actually implemented.

---

## 1. Recovery Invariants

These rules are more important than any individual command:

| Invariant | Why it exists |
| --- | --- |
| Preserve the failed physical run | Historical evidence is needed to distinguish source, orchestration, load, and modeling failures. |
| Never invent a replacement `pipeline_run_id` by hand | The normal Airflow plan binds IDs, dates, source files, immutable paths, and completion metadata together. |
| Do not blindly retry an ambiguous Glue submit | A timed-out `StartJobRun` response can still have created work remotely. Duplicate external submission is more dangerous than a clean replay. |
| Replay one logical date through the DAG | `replay_partition.py` is bounded to one date and creates fresh physical IDs without deleting prior publications. |
| Require exact Landing readiness before dbt | Files from another run, partial loads, duplicate file rows, or excess rows cannot satisfy the gate. |
| Close recovery with evidence | A green task alone is insufficient; validate the completion manifest, Landing gate, dbt result, run summary, and unified report. |

> [!NOTE]
> **Visual placeholder — Recovery flow.** Generate
> `docs/assets/runbook/recovery-flow.png` from brief **16** in
> [`docs/assets/README.md`](assets/README.md). Replace this note with the generated image once
> approved. The visual must show the CC0 replay path separately from live Spotify Lambda
> authentication/extraction recovery.

---

## 2. First Five Minutes: Identify the Failed Boundary

Start from the Airflow run and its persisted evidence. Do not infer pipeline success from one
S3 object, one Snowpipe load, or one successful downstream query.

| Symptom | Inspect first | Safe next action |
| --- | --- | --- |
| Live Spotify token refresh returns `invalid_grant` | Lambda structured failure event and secret age/state | Reauthorize interactively and replace the stored secret; do not reuse the rejected token. |
| Live Spotify returns HTTP 429 | Response reason, `Retry-After`, request cadence | Respect server guidance; distinguish transient throttling from quota exhaustion. |
| Source version changes during pagination | Lambda snapshot-mismatch failure | Abort the mixed-version attempt and start a fresh source execution. |
| Glue submit is uncertain | `submission.json`, task logs, Glue job runs | Investigate the claimed physical run before any replay. |
| Glue job fails | `glue-<pipeline_run_id>.json`, Glue state, completion metadata | Diagnose the job; use a new DAG run after the failed/ambiguous attempt is settled. |
| Landing sensor times out | Glue completion manifest, `landing-<pipeline_run_id>.json`, Snowflake `COPY_HISTORY` | Run the bounded read-only Landing audit and compare exact filenames/rows. |
| dbt build fails | `dbt-output.log`, dbt `run_results.json` | Fix the model/data contract, then replay the logical date through the normal DAG. |
| DAG misses its deadline | `DAG_DEADLINE_MISSED`, task states, latest run evidence | Find the slow/stalled boundary; the deadline event does not identify root cause by itself. |
| DAG fails | `DAG_FAILED`, task states, per-stage artifacts | Diagnose the first broken contract before replaying. |
| Unified report cannot be built | `plan.json`, `glue-*.json`, `landing-*.json`, `dbt-summary.json`, `run-summary.json` | Repair or regenerate the missing evidence through the producing stage; never fabricate fields. |

For a completed Airflow run, consolidate the evidence with:

```bash
.venv/bin/python scripts/generate_run_report.py \
  --run-key '<run-key>' \
  --json
```

The schema and evidence semantics live in [`OBSERVABILITY.md`](OBSERVABILITY.md).

---

## 3. Recovery Decision Sequence

Use this sequence before executing any replay:

1. **Freeze the physical identity.** Record `airflow_run_id`, `run_key`, and the affected
   `pipeline_run_id`.
2. **Find the last proven boundary.** Identify the newest trustworthy artifact: Bronze object,
   Glue submission claim, Glue completion manifest, Landing evidence, dbt results, or final
   run summary.
3. **Resolve ambiguity.** If an external operation may still be running, inspect the provider
   state before creating new work.
4. **Preview recovery.** Run the replay CLI in its default dry-run mode and review the exact
   Airflow command/date.
5. **Execute one clean attempt.** Use `--execute` only after the target date and provider
   state are understood.
6. **Re-prove downstream readiness.** Require the normal Glue completion, six-dataset exact
   Landing gate, dbt build, and final report.
7. **Compare attempts.** Verify the replay kept the intended logical date/source provenance and
   received a fresh physical run ID.

This sequence is intentionally conservative because the most expensive incident is one where
recovery destroys the evidence needed to understand the original failure.

---

## 4. Live Spotify Source Recovery

This section applies to the implemented Spotify Web API + Lambda path. It is **not** the
bounded CC0 demo replay path.

### 4.1 Invalid refresh token

An `invalid_grant` response means the current refresh token is no longer usable. Do not loop
on the rejected credential. Perform the interactive Authorization Code flow outside the
runtime, obtain a new refresh token, and replace the AWS Secrets Manager value.

### 4.2 Safe secret replacement

Do not place client credentials or refresh tokens directly in shell command arguments. The
following workflow prompts locally, writes a mode-`0600` temporary JSON file, sends that file
to AWS CLI, and removes it immediately afterward:

```bash
secret_file="$(mktemp)"
chmod 600 "$secret_file"
SECRET_FILE="$secret_file" .venv/bin/python - <<'PY'
import getpass
import json
import os

payload = {
    "client_id": getpass.getpass("Spotify client ID: "),
    "client_secret": getpass.getpass("Spotify client secret: "),
    "refresh_token": getpass.getpass("Spotify refresh token: "),
}
with open(os.environ["SECRET_FILE"], "w", encoding="utf-8") as handle:
    json.dump(payload, handle)
PY

aws secretsmanager put-secret-value \
  --secret-id spotify/api/credentials \
  --secret-string "file://$secret_file"

rm -f "$secret_file"
unset secret_file
```

After replacement, invoke the live extractor through its normal source path. A successful
refresh/source run is the recovery evidence; never print the token or secret payload to prove
that the update occurred.

### 4.3 429 and pagination version drift

For HTTP 429, respect `Retry-After` when supplied and avoid immediate retry loops when quota
is exhausted. The playlist-items client uses the supported bounded page size; raising page size
is not a recovery strategy.

If `spotify_snapshot_id` changes during pagination, allow the current attempt to fail. The
extractor protects atomicity by refusing to combine pages from different playlist versions.
Start a fresh physical source execution after the change settles.

---

## 5. Snowflake Credentials for Local Operations

The host-side Landing audit and the Airflow container receive credentials through different
process boundaries. Prefer key-pair authentication for repeatable local automation.

For a one-off host-side password session, prompt without echo:

```bash
printf 'Snowflake password: ' >&2
IFS= read -r -s SNOWFLAKE_PASSWORD
printf '\n' >&2
export SNOWFLAKE_PASSWORD

export SNOWFLAKE_ACCOUNT='<account-identifier>'
export SNOWFLAKE_USER='<service-user>'
export SNOWFLAKE_ROLE='SPOTIFY_TRANSFORMER'
export SNOWFLAKE_WAREHOUSE='COMPUTE_WH'
```

Remove the password from the shell when finished:

```bash
unset SNOWFLAKE_PASSWORD
```

The Airflow service reads the ignored `airflow/.env` file when Compose creates the
container. Host variables exported later are not injected into an already-created container.
Use `airflow/.env.example` as the template, keep the real file local and restricted to the
current user, and recreate the Airflow service after environment changes.

For key-pair auth, place the private key under ignored `airflow/secrets/` and reference its
read-only container path from `airflow/.env`. Never paste credentials into screenshots,
issues, run logs, or documentation examples.

---

## 6. Glue 5.1 Failure or Ambiguous Submission

The Glue submission task intentionally has `retries=0`. Before calling `StartJobRun`,
Airflow creates
`metadata/curation/<pipeline_run_id>/submission.json` with an immutable conditional write.
The claim survives an ambiguous client response and tells the operator that a physical
submission may already exist.

### If submission status is uncertain

1. Record the affected `pipeline_run_id` from `plan.json` or
   `glue-<pipeline_run_id>.json` when present.
2. Inspect `metadata/curation/<pipeline_run_id>/submission.json`.
3. Inspect AWS Glue job runs for the configured job and correlate the candidate execution.
4. Do **not** clear/retry the Glue submit task while the remote state is ambiguous.
5. If the old attempt is failed/stopped or otherwise settled, start a new Airflow DAG run for
   the logical date. The new run receives fresh physical IDs and paths.

### If Glue completed

Verify `metadata/curation/<pipeline_run_id>/complete.json` exists and that it contains:

- schema version `1`;
- matching run, playlist, snapshot date, and ingestion date lineage;
- all six Silver dataset inventories;
- valid run-scoped Parquet keys and non-negative row counts;
- exactly one playlist observation for the physical demo run;
- a non-negative `rejected_items` count.

For the bounded portfolio demo, any rejected item fails the pre-dbt quality gate.

Do not manually start Glue with a fabricated run ID. That bypasses the plan, immutable path,
and completion-manifest contracts used by Landing readiness.

---

## 7. Snowflake Landing Lag or Missing Rows

`scripts/audit_landing_lag.py` is the supported diagnostic utility for recent Snowpipe load
history. It queries bounded `INFORMATION_SCHEMA.COPY_HISTORY` for the six Landing tables and
accepts a lookback of 1–168 hours.

Preview the SQL without opening a Snowflake connection:

```bash
.venv/bin/python scripts/audit_landing_lag.py \
  --hours 24 \
  --dry-run
```

Run the read-only audit after configuring Snowflake authentication locally:

```bash
.venv/bin/python scripts/audit_landing_lag.py --hours 24
```

### What the exact Landing gate requires

The completion manifest is the expected inventory. For each of the six datasets, the sensor
accepts readiness only when the observed Snowflake rows correspond to the exact physical files
for the current run and their row counts match the Glue inventory.

The gate fails closed on:

- an unexpected filename;
- a repeated filename;
- duplicate `_FILE_ROW_NUMBER` values;
- more observed rows than Glue declared;
- lineage/completion-manifest mismatch;
- rejected demo source items.

Missing positive-row files remain **not ready** and keep the bounded sensor waiting until its
timeout. A zero-row file can be proven empty by the Glue completion inventory.

If COPY history shows a failed file, diagnose the Snowpipe/load error and the corresponding
Parquet object. An ad-hoc `COPY INTO` is not the default recovery path because it bypasses
the same evidence chain that makes duplicate/load reasoning reliable.

---

## 8. dbt Build or Data-Quality Failure

The dbt task runs only after every mapped physical run passes exact Landing readiness. When it
fails:

1. inspect the run-scoped `dbt-output.log` and dbt `run_results.json`;
2. identify the failing model or test and isolate the affected logical date/window;
3. determine whether the cause belongs to source quality, staging normalization,
   relationships, accepted values, or canonical grain;
4. fix the contract or model and validate locally;
5. replay the logical date through the normal DAG so Landing and dbt are re-proven in order.

The analytical fact grain is `(playlist_id, snapshot_date, track_position)`.
`pipeline_run_id` remains physical lineage. A clean replay can therefore write new immutable
physical files while dbt incremental merge converges on the same logical fact keys.

---

## 9. Safe Single-Date Replay

`scripts/replay_partition.py` is the supported recovery entry point for the bounded CC0
Airflow DAG. It currently accepts only `playlist_tracks`, requires an ISO `YYYY-MM-DD`
date, rejects future dates, and defaults to dry-run.

### 9.1 Preview first

This prints the exact `docker compose ... airflow dags trigger` command and exits without
starting the DAG:

```bash
.venv/bin/python scripts/replay_partition.py \
  --date 2026-09-10 \
  --entity playlist_tracks
```

Use `--dry-run` explicitly when a recorded operator procedure benefits from the visible
intent:

```bash
.venv/bin/python scripts/replay_partition.py \
  --date 2026-09-10 \
  --entity playlist_tracks \
  --dry-run
```

### 9.2 Pre-execution checklist

Confirm all of the following:

- the date is the intended logical snapshot date;
- the bounded CC0 manifest contains that date;
- `airflow/.env` has the required deployed AWS/Snowflake settings and one supported
  Snowflake authentication method;
- the Airflow service was recreated after any environment change;
- any ambiguous Glue submission for the prior attempt has been investigated and settled;
- you are intentionally replaying the **CC0 demo DAG**, not testing live Spotify Lambda
  extraction.

### 9.3 Execute one clean replay

```bash
.venv/bin/python scripts/replay_partition.py \
  --date 2026-09-10 \
  --entity playlist_tracks \
  --execute
```

The script triggers `spotify_daily_snapshot` with
`start_date=end_date=<requested-date>`. The new Airflow run creates fresh
`pipeline_run_id` values and new immutable Bronze/Silver physical paths. It does not delete
or overwrite prior successful or failed publications. Task retries within the same Airflow run
retain that run's physical IDs.

### 9.4 Prove recovery

After the DAG succeeds:

1. verify the Glue completion manifest for the new physical run;
2. verify all six Landing datasets report exact readiness;
3. verify dbt completed with only `success`/`pass` result states;
4. verify `run-summary.json` reports `success`;
5. generate the new `pipeline-run-report.json`;
6. compare the prior and replay reports: logical date/source version should remain intentional,
   while `pipeline_run_id` and physical paths should be new.

---

## 10. Airflow Deadline and Failure Events

The DAG uses Airflow 3 Task SDK reliability controls:

| Control | Current contract |
| --- | --- |
| Default safe-task retry | 3 retries, five-minute initial delay, exponential backoff. |
| Glue submit | No Airflow retry. |
| Glue sensor | Reschedule mode, 30-second interval, 60-minute timeout. |
| Landing sensor | Reschedule mode, 30-second interval, 15-minute timeout. |
| DAG run timeout | Two hours. |
| Deadline Alert | Two hours from `DAGRUN_QUEUED_AT`. |
| Failure event | `DAG_FAILED`. |
| Deadline event | `DAG_DEADLINE_MISSED`. |

The callback payload is deliberately small: timestamp, component, failure status, DAG/task/run
identifiers, try number, and exception class when available. Exception message/body and
credentials are not serialized.

Interpret the events carefully:

- `DAG_FAILED` says the orchestration run failed; use task state and stage evidence to locate
  the broken contract.
- `DAG_DEADLINE_MISSED` says the configured completion deadline elapsed; it is a latency
  signal, not a statement that every task failed.
- Neither event by itself proves CloudWatch alarm delivery, a pager notification, or a
  dashboard. Those require separate deployment evidence.

---

## 11. Recovery Completion Checklist

Do not close the incident until the successful attempt is independently reconstructable:

- [ ] Airflow `run_id` and `run_key` are known.
- [ ] The intended logical date/window and source provenance are known.
- [ ] Every physical run has a valid Glue completion manifest.
- [ ] `rejected_items=0` for the bounded CC0 demo.
- [ ] All six Landing datasets pass exact filename/row readiness.
- [ ] dbt finished with all result nodes in `success`/`pass` state.
- [ ] `run-summary.json` reports `success`.
- [ ] `pipeline-run-report.json` validates and reflects the recovered run.
- [ ] The replay has fresh physical IDs while retaining the intended logical business grain.
- [ ] Any locally exported password is unset and temporary credential files are removed.
- [ ] Any live-source recovery claim is supported by live-source evidence, not by the CC0 demo.

Power BI/dashboard validation is a separate serving concern and is not part of incident closure
for this pipeline.
