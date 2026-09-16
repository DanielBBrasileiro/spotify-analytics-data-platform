# Operational Runbook & Incident Response

This runbook covers the repository's current recovery path for Spotify authentication,
immutable Bronze/Silver publication, Glue 5.1, Snowflake Landing, dbt, and Airflow 3.
Recovery is evidence-first: identify the failed physical run, inspect its persisted evidence,
then replay through the normal DAG with fresh physical IDs when a new attempt is required.

---

## 1. First Response: Identify the Failed Boundary

Start with the Airflow run and its artifact directory. Do not infer success from the presence
of one downstream file.

| Symptom | Inspect first | Typical next action |
| --- | --- | --- |
| Spotify token refresh returns `invalid_grant` | Lambda structured failure event and credential age | Reauthorize interactively and replace the stored secret. |
| Spotify returns HTTP 429 | Response reason/header and request cadence | Distinguish quota exhaustion from transient rate limiting before retrying. |
| Glue task stalls/fails | `glue-<pipeline_run_id>.json`, Glue run state, S3 submission/completion metadata | Investigate the exact Glue run; replay via a new DAG run if needed. |
| Landing sensor times out | `landing-<pipeline_run_id>.json` when present and Snowflake COPY history | Run the bounded Landing audit; verify exact run-scoped files. |
| dbt build fails | `dbt-output.log`, `dbt/run_results.json`, `dbt-summary.json` if created | Fix the data/model cause, then replay the logical date/window. |
| DAG misses its completion deadline | Structured `DAG_DEADLINE_MISSED` callback plus task states | Find the slow/stalled component before starting a new run. |
| Unified report cannot be generated | `plan.json`, `glue-*.json`, `landing-*.json`, `dbt-summary.json`, `run-summary.json` | Repair the missing/incomplete evidence source; do not fabricate report fields. |

For a completed run, consolidate the evidence with:

```bash
.venv/bin/python scripts/generate_run_report.py --run-key '<run-key>' --json
```

See [`OBSERVABILITY.md`](OBSERVABILITY.md) for the report schema and evidence semantics.

---

## 2. Spotify Authentication Recovery

The live extractor uses Spotify Authorization Code Flow with a refresh token. As of the 2026
Spotify Web API documentation, access tokens expire after one hour and Developer Dashboard
refresh tokens have a six-month lifetime. An `invalid_grant` response means the rejected
refresh token must not be retried indefinitely; operator reauthorization is required.

The repository does not automate browser consent. Perform the one-time Authorization Code
Flow outside the runtime, obtain the new `refresh_token`, then update AWS Secrets Manager.

### Safely replace the AWS secret

Do not place client credentials or refresh tokens directly in shell command arguments. The
workflow below prompts locally, writes a mode-`0600` temporary JSON file, sends that file to
AWS CLI, and deletes it immediately afterward:

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

After replacement, invoke the extractor through its normal path. A successful refresh proves
the stored token is usable; do not print the token or secret payload as a verification step.

### Spotify 429 handling

Treat quota and rate limiting separately:

- `reason=QUOTA_EXCEEDED` indicates the Development Mode quota pool is exhausted. Repeated
  immediate retries only consume time; reduce request volume and wait for quota availability.
- A transient 429 with a `Retry-After` header should respect that delay.
- The playlist items endpoint supports at most `limit=50`, so increasing page size above 50
  is not a valid mitigation.

If playlist metadata changes during pagination and the extractor raises a snapshot mismatch,
allow the attempt to fail atomically and start a fresh physical run. Do not merge pages from
two source versions.

---

## 3. Local Snowflake Authentication Without Shell-History Leakage

The Landing audit and local Airflow stack accept either key-pair authentication or a password,
but they receive environment variables in different processes. Key-pair authentication is
preferred for repeatable automation. For the host-side audit utility, prompt without echo and
export only into the current shell process:

```bash
printf 'Snowflake password: ' >&2
IFS= read -r -s SNOWFLAKE_PASSWORD
printf '\n' >&2
export SNOWFLAKE_PASSWORD
```

Configure the non-secret connection values separately:

```bash
export SNOWFLAKE_ACCOUNT='<account-identifier>'
export SNOWFLAKE_USER='<service-user>'
export SNOWFLAKE_ROLE='SPOTIFY_TRANSFORMER'
export SNOWFLAKE_WAREHOUSE='COMPUTE_WH'
```

When finished with local Snowflake commands:

```bash
unset SNOWFLAKE_PASSWORD
```

Do not put a real password in copied terminal commands, issue comments, screenshots, or
documentation. The Airflow service reads the ignored `airflow/.env` file when Compose creates
the container, so host-shell variables exported later are not injected automatically. Use the
committed `airflow/.env.example` as the local template, restrict `airflow/.env` to the current
user, edit it locally, and recreate the Airflow service after environment changes. For key-pair
auth, place the protected key under ignored `airflow/secrets/` and reference its read-only
container path from `airflow/.env`.

---

## 4. Glue 5.1 Failure or Ambiguous Submission

The Glue submission task is intentionally configured with `retries=0`. Before starting Glue,
Airflow writes an immutable submission claim under the run's curation metadata. This prevents
an ambiguous `StartJobRun` timeout from being blindly retried against the same physical
publication prefix.

When Glue fails or submission status is uncertain:

1. Record the affected `pipeline_run_id` from `plan.json` or `glue-<pipeline_run_id>.json`.
2. Inspect the corresponding Glue job run and
   `metadata/curation/<pipeline_run_id>/submission.json` in S3.
3. If Glue completed, verify `metadata/curation/<pipeline_run_id>/complete.json` exists and
   contains all six Silver datasets plus a non-negative `rejected_items` count.
4. If the attempt is irrecoverably failed or ambiguous, replay the logical date through
   `scripts/replay_partition.py`. The new DAG run receives fresh physical IDs and paths.

Avoid manually starting the same Glue job with an invented run ID. The normal DAG carries the
validated date, playlist, immutable path, and completion-manifest contracts that downstream
Landing checks rely on.

---

## 5. Snowflake Landing Lag or Missing Files

`scripts/audit_landing_lag.py` inspects bounded Snowflake `COPY_HISTORY` for all six Landing
tables. It is read-only and accepts a lookback of 1 to 168 hours.

Preview the exact SQL without connecting to Snowflake:

```bash
.venv/bin/python scripts/audit_landing_lag.py --hours 24 --dry-run
```

After configuring Snowflake authentication locally, execute the audit:

```bash
.venv/bin/python scripts/audit_landing_lag.py --hours 24
```

Interpret the result alongside the Glue completion manifest. Landing readiness is based on
exact run-scoped filenames and row counts; a file from another run or a partial load does not
satisfy the gate.

If COPY history shows a failed file, investigate the Snowpipe/load error and the corresponding
Parquet object. If notifications are delayed, allow the bounded sensor window to resolve or
start a clean replay after diagnosing the cause. Do not use an ad-hoc `COPY INTO` as the first
recovery action because it bypasses the normal evidence path and can complicate duplicate-file
reasoning.

---

## 6. dbt Build or Data-Quality Failure

The dbt task runs only after exact Landing readiness. On failure:

1. Inspect the run-scoped `dbt-output.log` and `dbt/run_results.json` under the Airflow artifact
   directory.
2. Identify the failing model/test and query only the affected logical date/window.
3. Check whether the failure originates from source quality, staging normalization,
   referential integrity, or canonical fact grain.
4. Fix the root cause in code/data contracts and rerun tests locally.
5. Replay the logical date/window through the DAG so Landing checks and dbt build execute in
   their normal order.

The canonical fact grain is playlist + snapshot date + track position. Physical
`pipeline_run_id` values remain lineage; they are not part of the business grain. A replay can
therefore create new physical files while dbt incremental merge converges on the same logical
fact keys.

---

## 7. Safe Partition Replay

`scripts/replay_partition.py` accepts one ISO date and currently supports the
`playlist_tracks` entity. Dates in the future are rejected.

Dry-run is the default. This command prints the exact Airflow trigger without executing it:

```bash
.venv/bin/python scripts/replay_partition.py \
  --date 2026-09-10 \
  --entity playlist_tracks
```

`--dry-run` may be supplied explicitly for operator clarity:

```bash
.venv/bin/python scripts/replay_partition.py \
  --date 2026-09-10 \
  --entity playlist_tracks \
  --dry-run
```

Before executing, confirm:

- the date is the intended logical snapshot date;
- the CC0 demo manifest contains that date when using the portfolio DAG;
- ignored `airflow/.env` contains the required deployed AWS/Snowflake settings and one supported
  Snowflake authentication method;
- the Airflow service was recreated after any environment change;
- no unresolved ambiguous Glue submission exists that still needs investigation.

Execute only after reviewing the printed command:

```bash
.venv/bin/python scripts/replay_partition.py \
  --date 2026-09-10 \
  --entity playlist_tracks \
  --execute
```

The replay triggers `spotify_daily_snapshot` with `start_date=end_date=<date>`. A new DAG run
creates a fresh `pipeline_run_id`; it does not delete or overwrite prior Bronze/Silver
publications. Task retries inside one DAG run keep the same physical IDs.

After the replay succeeds, create/inspect its unified report and compare logical date,
source-version provenance, Landing readiness, row counts, and dbt result with the prior run.

---

## 8. Airflow Retries, Sensors, and Deadline Alerts

The current DAG uses Airflow 3 Task SDK behavior:

- default tasks: three retries, five-minute initial delay, exponential backoff;
- Glue submission: no task retry, by design;
- Glue sensor: 30-second reschedule interval, one-hour timeout;
- Landing sensor: 30-second reschedule interval, 15-minute timeout;
- DAG run: two-hour timeout;
- Deadline Alert: two hours from `DAGRUN_QUEUED_AT`;
- structured callbacks: `DAG_FAILED` and `DAG_DEADLINE_MISSED`.

The Deadline Alert is the Airflow 3 replacement for legacy SLA syntax. If it fires, use it as
an investigation signal rather than proof that every task failed. Review task states and the
latest persisted evidence to find the slow boundary.

---

## 9. Recovery Completion Checklist

Before considering an incident resolved:

- [ ] The successful attempt has a known Airflow `run_id`/`run_key`.
- [ ] Every requested logical date has a physical run with a valid Glue completion manifest.
- [ ] `rejected_items` is zero for the bounded portfolio demo.
- [ ] All six Landing datasets pass exact file/row readiness.
- [ ] dbt build completed with all result nodes in `success`/`pass` state.
- [ ] `run-summary.json` reports success.
- [ ] `pipeline-run-report.json` validates and reflects the recovered run.
- [ ] Any locally exported password has been unset and temporary credential files were removed.

Power BI/dashboard validation is outside this incident runbook and must be evidenced separately
before it is described as tested.
