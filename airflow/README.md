# Local Airflow orchestration

Implements the bounded CC0 workflow for issues #23–#25 and the minimum gates/reporting
from #27–#28. Power BI is a future consumer; no dashboard is required to run this pipeline.

## Execution

`prepare → records → [upload → submit → await_glue → await_landing] per snapshot → transform → report`

- Airflow **3.2.2 / Python 3.12**, Task SDK, local `standalone` with PostgreSQL/LocalExecutor.
- Manual triggers only (`schedule=None`), one active Dag run. No cloud resources are created.
- The existing Glue job processes Bronze; Snowpipe loads Silver; dbt computes analytics.
- Every requested date must exist in the generated CC0 manifest (maximum window: 31 days).
- Glue jobs queue behind the deployed job's concurrency limit; the default demo has three dates.
- Sensors reschedule instead of occupying a worker while waiting. Glue wait: 60 minutes;
  Landing wait: 15 minutes; dbt: 30 minutes; whole Dag: two hours.
- AWS/Snowflake settings are resolved during task execution, never during DAG parsing.

## First setup

From the repository root:

```bash
# Existing CC0 source, downloaded separately as documented in scripts/README.md.
.venv/bin/python scripts/generate_cc0_playlist_bronze.py \
  --csv-path tmp/spotify10000/data.csv --output-root tmp/cc0-cloud-demo \
  --start-date 2026-09-10 --track-limit 12
cp airflow/.env.example airflow/.env
# Fill the local .env with deployed bucket/job names and authorized credentials.
make airflow-up
```

`make airflow-up` builds the image and starts local services. The Dockerfile uses a multi-stage
`python:3.12-slim-bookworm` base and installs the pinned Airflow 3.2.2 runtime directly, so the
image builds natively on both x86_64 and Apple Silicon instead of relying on x86 emulation.
Open http://localhost:8080.
The local username is `admin`; Airflow writes its generated password to the state volume's
`/opt/airflow/state/passwords.json`. Read it locally; do not paste it into tickets or logs.
The UI is bound to loopback. This Compose environment is for local development, not a
production deployment. Docker needs sufficient free disk and memory for the image.

The image isolates dbt in its own virtual environment and installs pinned dbt packages at
build time; build-only Rust/C toolchains stay out of the final runtime image. Rebuild after
changing DAG/runtime/dbt/source code. Runtime artifacts and logs
are bind-mounted separately. PostgreSQL and local auth state survive `make airflow-down`.

### Existing cloud prerequisites

1. The bounded S3/Glue/Snowflake/Snowpipe deployment already exists and is enabled.
2. Deploy the updated `glue/jobs/bronze_to_silver_curation.py` **and** a runtime ZIP containing
   the `glue/` package, including `glue/storage/completion.py`. Old deployed jobs do not emit
   the completion manifest, so the new DAG intentionally fails if they are used.
3. Glue `MaxRetries=0`: each physical publication is written once. Its role needs its
   existing Bronze/Silver permissions, `s3:GetObject` on Silver and scoped `s3:ListBucket`
   for the Parquet inventory, plus `s3:PutObject` on `metadata/curation/*`.
4. The Airflow identity needs `s3:PutObject`/`s3:GetObject` on the run-scoped Bronze and
   `metadata/curation/*` prefixes, and `glue:GetJob`, `glue:StartJobRun`, `glue:GetJobRun`
   on the configured job. No infrastructure-creation permissions are used.
5. Snowflake credentials must have the existing `SPOTIFY_TRANSFORMER` role. The gate reads
   Landing; dbt creates the serving views with the same role. Existing analyst grants
   already include future MARTS views.
6. Optional key-pair authentication: place the key under ignored `airflow/secrets/` and set
   `SNOWFLAKE_PRIVATE_KEY_PATH=/opt/airflow/secrets/<filename>`. Temporary AWS credentials
   and Snowflake passwords can also be supplied in ignored `airflow/.env`.

## Trigger and replay

```bash
docker compose -f airflow/docker-compose.yml exec airflow \
  airflow dags unpause spotify_daily_snapshot
docker compose -f airflow/docker-compose.yml exec airflow \
  airflow dags trigger spotify_daily_snapshot \
  --conf '{"start_date":"2026-09-10","end_date":"2026-09-12"}'
```

For one date, pass the same `start_date` and `end_date`. A new Dag run gives each physical
snapshot a new UUID and S3 prefix. Retrying `prepare`/`upload` preserves the same UUID and
validates identical Bronze bytes. Original source metadata is not rewritten.

**Do not clear `curate.submit` to retry Glue.** Submission creates an immutable S3 claim
before `StartJobRun`, disables SDK retries for that call, and has no Airflow retry. If the
response is ambiguous, inspect Glue runs and the task logs; start a new Dag run after the
old job has stopped. This prevents duplicate execution and rewriting files already tracked
by Snowpipe. Sensors can be cleared to resume checking an existing job. The Glue job itself
has a 15-minute compute timeout; stopping Airflow does not cancel cloud jobs.

## Pre-dbt quality gate

After all six datasets are written, Glue inventories actual Parquet filenames and row counts
and writes `metadata/curation/<physical-run-id>/complete.json`. No marker is published if
curation or inventory fails. The gate verifies:

- Manifest version, playlist/date/run lineage, all six datasets and physical path boundaries.
- Exactly one playlist observation and zero rejected source items for this demo.
- Every expected nonempty file has exactly its expected Landing row count, with no repeated
  `_FILE_ROW_NUMBER`. Unexpected files and excess rows fail immediately; missing rows wait.
- Empty Parquet files are explicitly recorded with zero rows. An empty dataset does not
  incorrectly require a non-existent Landing row.

All mapped gates must pass before `dbt build`. Existing dbt business tests and new serving
coverage/uniqueness tests then run together. Any warning, skipped node, error or missing
result prevents a successful run summary.

This workflow assumes exclusive publication to its UUID prefixes. Completion evidence is
local to each physical run; existing rows from another run cannot satisfy the readiness gate.

## Evidence and consumption

`airflow/artifacts/<hash-of-dag-run-id>/` contains the plan, Glue job IDs, per-run completion
inventory/readiness, dbt output, `run_results.json`, and `run-summary.json`. The final task
runs after upstream failure and raises on incomplete work, so an `all_done` leaf cannot
turn a failed pipeline green. These artifacts are ignored by Git.

A successful summary is the refresh handoff for future consumers. dbt builds are not an
atomic swap of the entire MARTS schema: consumers should refresh only after success.
See [the serving contract](../docs/SERVING_CONTRACT.md).

## Validation

```bash
.venv/bin/python -m venv .venv-airflow
.venv-airflow/bin/pip install apache-airflow==3.2.2 pytest -r airflow/requirements.txt \
  --constraint https://raw.githubusercontent.com/apache/airflow/constraints-3.2.2/constraints-3.12.txt
make airflow-test
```

The suite loads the real DAG, exercises the Task SDK scheduler loop with mocked cloud
boundaries, and tests immutable uploads, submission claims, sensor outcomes and exact file
readiness. It does not substitute for a live AWS/Snowflake smoke run. CI runs the same suite.

Runtime design references: [Airflow Docker deployment](https://airflow.apache.org/docs/apache-airflow/3.2.2/howto/docker-compose/)
and [Task SDK](https://airflow.apache.org/docs/task-sdk/stable/api.html).
