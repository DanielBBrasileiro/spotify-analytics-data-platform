# Apache Airflow 3 Orchestration

This directory contains the local orchestration runtime for the validated bounded portfolio path:

```text
CC0-backed Bronze input → S3 → Glue 5.1 → Snowpipe / Snowflake Landing → dbt → serving views
```

Airflow is used as a **coordinator and evidence producer**, not as the data-processing engine. Heavy work stays in AWS Glue and Snowflake/dbt.

The DAG is intentionally manual (`schedule=None`) so live cloud runs remain explicit, bounded and cost-controlled.

---

## 1. Runtime at a Glance

| Concern | Implementation |
|---|---|
| Airflow | **3.2.2** |
| Python | **3.12** |
| Authoring | Airflow 3 Task SDK (`airflow.sdk`) |
| Executor | `LocalExecutor` |
| Metadata DB | PostgreSQL 16 |
| Local packaging | Docker Compose |
| DAG | `spotify_daily_snapshot` |
| Schedule | `None` — explicit manual execution |
| Active DAG runs | `max_active_runs=1` |
| Active tasks | `max_active_tasks=4` |
| DAG timeout | 2 hours |
| Deadline Alert | 2 hours from `DAGRUN_QUEUED_AT` |

The Docker image is built natively from `python:3.12-slim-bookworm`; dbt is isolated in its own virtual environment inside the runtime image.

---

## 2. DAG Execution Model

<!--
VISUAL ASSET 10
Target: docs/assets/airflow/spotify-daily-snapshot-dag-flow.png
Prompt: docs/assets/README.md#10--detailed-airflow-dag-flow
When ready:
![spotify_daily_snapshot DAG Flow](../docs/assets/airflow/spotify-daily-snapshot-dag-flow.png)
-->

```text
prepare
  │
  ▼
records
  │
  ├─ snapshot A: upload → submit → await_glue → await_landing ┐
  ├─ snapshot B: upload → submit → await_glue → await_landing ├─ all ready
  └─ snapshot C: upload → submit → await_glue → await_landing ┘
                                                               │
                                                               ▼
                                                           transform
                                                               │
                                                               ▼
                                                             report
```

The mapped curation group is expanded once per requested logical snapshot date. Each mapped record owns a fresh physical `pipeline_run_id` and its own immutable Bronze/Silver evidence.

### Task contract

| Task | Responsibility | Retry model | External side effect |
|---|---|---|---|
| `prepare` | Validate runtime configuration, date window and manifest; create immutable physical plan. | Default safe retries | Local evidence only. |
| `records` | Expose planned snapshot records for task mapping. | Default safe retries | None. |
| `curate.upload` | Publish exact planned Bronze bytes to run-scoped S3 key. | Default safe retries with byte-identity guard | S3 `PutObject`. |
| `curate.submit` | Claim and submit one Glue job for the physical record. | **0 retries** | `StartJobRun`. |
| `curate.await_glue` | Wait for external Glue completion. | Sensor, `reschedule`, 60-minute timeout | Read-only status checks. |
| `curate.await_landing` | Prove exact Snowflake Landing readiness. | Sensor, `reschedule`, 15-minute timeout | Read-only Snowflake/S3 evidence checks. |
| `transform` | Execute dbt build after every mapped Landing gate passes. | 1 retry, 35-minute timeout | Snowflake transformations/tests. |
| `report` | Persist final status and evidence inventory. | 0 retries; `all_done` | Local evidence only. |

The `report` task is deliberately the only leaf. It runs after upstream failure to produce evidence, but raises when `transform` did not succeed, so `all_done` cannot accidentally turn a failed pipeline green.

---

## 3. Physical Run Identity and Replay

The DAG separates orchestration identity, physical processing identity and source identity.

| Identifier | Meaning |
|---|---|
| `airflow_run_id` | One DAG run covering a bounded date window. |
| `pipeline_run_id` | One physical snapshot-processing attempt; UUID v4. |
| `spotify_snapshot_id` | Upstream source version or explicit simulated version in the CC0 demo. |
| `snapshot_date` | Logical business observation date. |

Within one DAG run, task retries preserve the same physical ID. A new replay creates a new physical ID and therefore a new immutable evidence path.

The analytical model does **not** use `pipeline_run_id` as part of the business grain. dbt converges on:

```text
(playlist_id, snapshot_date, track_position)
```

That is why a replay can preserve forensic lineage without duplicating the business fact.

---

## 4. Reliability Controls

<!--
VISUAL ASSET 11
Target: docs/assets/airflow/reliability-controls.png
Prompt: docs/assets/README.md#11--airflow-reliability-controls
When ready:
![Airflow Reliability Controls](../docs/assets/airflow/reliability-controls.png)
-->

### Safe default retries

Safe tasks inherit three retries, a five-minute initial delay, exponential backoff and a five-minute default execution timeout. Retries are not applied mechanically to every external call.

### Why Glue submission has no generic retry

`curate.submit` uses `retries=0`, and the AWS SDK call to `StartJobRun` also disables automatic retries.

An external submission can succeed even when the client loses the response. A blind retry could then launch a second job against the same physical publication. The pipeline therefore creates an immutable submission claim, performs one external submit attempt, records the returned Glue run ID when available, and requires operator inspection when submission outcome is ambiguous.

**Do not clear `curate.submit` as a generic retry strategy.** Sensors may be cleared to resume checking an already-known external run.

### Deadline Alert

Airflow 3.2.2 configures a `DeadlineAlert` referenced to `DAGRUN_QUEUED_AT` with a two-hour interval. The project does not use legacy `sla=` syntax.

### Structured failure callbacks

The DAG-level failure and deadline callbacks emit compact `DAG_FAILED` and `DAG_DEADLINE_MISSED` events. Only safe scalar execution context is emitted: DAG/task/run identifiers, try number, timestamp and exception class. Exception messages and credentials are not serialized into the structured event.

---

## 5. Pre-dbt Readiness Gate

Glue success is necessary but not sufficient.

After curation, Glue writes `metadata/curation/<pipeline_run_id>/complete.json`, inventorying all six Silver datasets: `artists`, `albums`, `tracks`, `track_artists`, `playlist_snapshots`, and `playlist_observations`.

Before dbt can start, `curate.await_landing` verifies manifest version and lineage, exact physical paths and filenames, expected row counts, distinct Snowflake `_FILE_ROW_NUMBER` values, absence of unexpected rows/files, one playlist observation for the bounded demo, and zero rejected demo items.

Missing positive-row files keep the sensor waiting. Duplicates, excess rows, invalid completion metadata or rejected demo items fail closed. Empty datasets are represented explicitly with zero-row inventory entries.

---

## 6. Evidence Contract

Each DAG run writes small JSON evidence files under `airflow/artifacts/<hash-of-airflow-run-id>/`:

```text
plan.json
glue-<pipeline_run_id>.json
landing-<pipeline_run_id>.json
dbt-summary.json
run-summary.json
dbt/...
```

`plan.json` proves the requested window and physical IDs. Glue/Landing evidence connects external execution to exact warehouse readiness. `dbt-summary.json` records the build result, and `run-summary.json` is the final DAG-level handoff.

Consolidate a run with:

```bash
.venv/bin/python scripts/generate_run_report.py --run-key '<run-key>' --json
```

See [`../docs/OBSERVABILITY.md`](../docs/OBSERVABILITY.md).

---

## 7. Local Runtime

Docker Compose starts PostgreSQL 16 plus one Airflow standalone container running API server, scheduler, DAG processor and triggerer with `LocalExecutor`. Logs, evidence, demo data and read-only secrets are mounted separately; metadata/state volumes persist across `make airflow-down`.

The API/UI binds to `127.0.0.1:8080`. If that host port is already occupied, use a local override rather than stopping unrelated environments. The validated portfolio run used an alternate host port for that reason; the container-internal Airflow port remained 8080.

This Compose stack is a **local development/demo runtime**, not a production Airflow deployment.

---

## 8. First Setup

Prepare the deterministic CC0 demo manifest if needed:

```bash
.venv/bin/python scripts/generate_cc0_playlist_bronze.py \
  --csv-path tmp/spotify10000/data.csv \
  --output-root tmp/cc0-cloud-demo \
  --start-date 2026-09-10 \
  --track-limit 12
```

Create the ignored local integration file:

```bash
cp airflow/.env.example airflow/.env
```

The runtime expects `AWS_DEFAULT_REGION`, `SPOTIFY_LAKE_BUCKET`, `SPOTIFY_GLUE_JOB_NAME`, `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, and either `SNOWFLAKE_PRIVATE_KEY_PATH` or `SNOWFLAKE_PASSWORD`.

Temporary AWS credentials may be placed in ignored `airflow/.env` when required. Prefer Snowflake key-pair authentication with a key mounted read-only from `airflow/secrets/`. Never commit either location with real credentials.

Start the stack:

```bash
make airflow-up
```

Airflow starts paused by default. The local `admin` password is written inside the state volume at `/opt/airflow/state/passwords.json`; read it locally and never paste it into tickets, logs or documentation.

---

## 9. Existing Cloud Prerequisites

The bounded orchestration demo coordinates pre-existing resources. `make airflow-up` does **not** create cloud infrastructure.

The runtime expects an S3 lake bucket; the current Glue job and runtime package; scoped Airflow S3/Glue permissions; Snowpipe/Landing objects for the six datasets; and Snowflake credentials with `SPOTIFY_TRANSFORMER` capability for Landing validation and dbt build.

The Glue job itself uses `MaxRetries=0`; physical publications are intentionally not retried underneath Airflow without explicit orchestration semantics.

---

## 10. Triggering a Bounded Run

```bash
docker compose -f airflow/docker-compose.yml exec airflow \
  airflow dags unpause spotify_daily_snapshot

docker compose -f airflow/docker-compose.yml exec airflow \
  airflow dags trigger spotify_daily_snapshot \
  --conf '{"start_date":"2026-09-10","end_date":"2026-09-12"}'
```

For one logical date, pass the same value for `start_date` and `end_date`.

---

## 11. Safe Replay CLI

Prefer the repository recovery wrapper rather than hand-building DAG commands:

```bash
.venv/bin/python scripts/replay_partition.py \
  --date 2026-09-10 \
  --dry-run
```

Dry-run is the default behavior. `--execute` is required to trigger a new DAG run. See [`../docs/RUNBOOK.md`](../docs/RUNBOOK.md) before replaying a failed or ambiguous external submission.

---

## 12. Validation

```bash
make airflow-test
```

CI additionally runs `docker compose -f airflow/docker-compose.yml config --quiet` and the orchestration contract suite. Tests cover DAG parsing, dependency order, retries, Deadline configuration, service adapters, immutable uploads, submission claims, Glue state handling, exact Landing readiness and a real Task SDK DAG test with mocked external cloud boundaries.

These contracts complement rather than replace the bounded live AWS/Snowflake run captured for the portfolio release.

---

## 13. Operational References

- [`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md) — system boundaries and validated architecture.
- [`../docs/OBSERVABILITY.md`](../docs/OBSERVABILITY.md) — evidence schema and run report.
- [`../docs/RUNBOOK.md`](../docs/RUNBOOK.md) — incident triage and replay.
- [`../docs/SERVING_CONTRACT.md`](../docs/SERVING_CONTRACT.md) — downstream refresh/consumption contract.
- [Airflow 3 Docker deployment](https://airflow.apache.org/docs/apache-airflow/3.2.2/howto/docker-compose/)
- [Airflow Task SDK](https://airflow.apache.org/docs/task-sdk/stable/api.html)
