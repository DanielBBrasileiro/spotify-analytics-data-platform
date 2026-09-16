# Observability & Pipeline Evidence

Observability in v1.0.0 is built around **reconstructable evidence**, not a dashboard screenshot.
The repository records enough immutable and run-scoped metadata to answer four operational
questions: what logical snapshot was requested, which physical execution produced each file,
whether every expected Landing row arrived, and whether the downstream dbt build completed.

The evidence boundary is deliberately explicit. The validated public portfolio path is a
**bounded CC0-backed demo with synthetic temporal evolution**. The Spotify Web API + Lambda
source path is implemented and contract-tested, but its structured events are a separate
source-side surface; the CC0 run report must never be presented as proof that live Spotify
extraction ran.

> [!IMPORTANT]
> **v1.0.0 truth boundary:** no Grafana, CloudWatch dashboard, alarm delivery, or Power BI
> dashboard is claimed here. Structured events and persisted run evidence are the implemented
> observability products. Any managed log transport or dashboard requires its own deployment
> evidence.

---

## 1. Evidence Architecture

> [!NOTE]
> **Visual placeholder — Unified run telemetry.** Generate
> `docs/assets/observability/unified-run-telemetry.png` from brief **15** in
> [`docs/assets/README.md`](assets/README.md). Replace this note with the generated image once
> approved. The visual must keep the CC0 bounded path separate from the optional live Spotify
> Lambda telemetry path.

The batch path uses a chain of small evidence artifacts rather than a centralized monitoring
service:

```text
Airflow plan
   │
   ├─ one physical pipeline_run_id per playlist/date
   │      │
   │      ├─ immutable Bronze publication
   │      ├─ Glue submission claim + Glue job metadata
   │      ├─ Glue completion manifest with six Silver inventories
   │      └─ exact Snowflake Landing readiness evidence
   │
   ├─ dbt run_results summary
   └─ final run summary
          │
          ▼
   pipeline-run-report.json
          │
          └─ optional immutable S3 publication under metadata/pipeline_runs/
```

This design keeps the strongest evidence close to the operation that produced it. A final
report consolidates those facts; it does not manufacture missing telemetry.

---

## 2. Correlation Model

The identifiers intentionally describe different layers of identity:

| Identifier | Question answered | Contract |
| --- | --- | --- |
| `airflow_run_id` | Which orchestration attempt is this? | Assigned by Airflow for one DAG run and bounded date window. |
| `run_key` | Where can that Airflow run be stored safely? | First 32 hex characters of a SHA-256-derived key from `airflow_run_id`. |
| `pipeline_run_id` | Which physical playlist/date publication produced these files? | UUID v4; fresh for a new DAG run and stable across retries inside that run. |
| `spotify_snapshot_id` | Which source version does this observation represent? | Spotify source version on the live path; explicitly simulated source version in the CC0 demo. |
| `snapshot_date` | What logical observation date does analytics use? | Business date; independent from the physical execution ID. |

### The invariant that makes replay safe

A replay keeps the **logical identity** and creates a new **physical identity**. A new Airflow
run for the same date gets fresh `pipeline_run_id` values and new run-scoped Bronze/Silver
paths. dbt still converges on the canonical business grain
`(playlist_id, snapshot_date, track_position)`.

This separation prevents operational retries from becoming duplicate analytical facts while
preserving a complete physical audit trail.

---

## 3. Two Observability Surfaces

### 3.1 Spotify Lambda structured telemetry

When the live-source Lambda path is invoked, it emits compact single-line JSON lifecycle
events. Every event carries a stable correlation envelope:

| Field | Contract |
| --- | --- |
| `timestamp` | UTC ISO-8601 emission time. |
| `event` | Stable lifecycle event name. |
| `level` | `INFO` or `ERROR`. |
| `source` | `spotify_web_api`. |
| `component` | `lambda`. |
| `pipeline_version` | Repository package version. |
| `pipeline_run_id` | UUID v4 physical execution identifier. |
| `playlist_id` | 22-character playlist identifier. |
| `spotify_snapshot_id` | Source version once known; otherwise `null`. |
| `snapshot_date` | Logical observation date. |
| `duration_ms` | Non-negative duration for the event scope. |
| `status` | `RUNNING`, `SUCCESS`, or `FAILED`. |

Lifecycle events extend that envelope only with bounded scalar fields:

| Event | Additional fields | Operational meaning |
| --- | --- | --- |
| `EXTRACTION_START` | none | Playlist processing started; source version may still be unknown. |
| `PAGINATION_PAGE_FETCHED` | `page_number`, `offset`, `records_in_page`, `total_records` | A page passed pagination/source-version checks. |
| `S3_WRITE_SUCCESS` | `records_extracted`, `s3_uri` | Immutable Bronze publication succeeded. |
| `EXTRACTION_COMPLETE` | `records_extracted`, `snapshot_timestamp` | Source extraction and Bronze landing completed. |
| `EXTRACTION_FAILED` | `error_type` | Sanitized failure record; exception text/body is not copied into telemetry. |

The logger owns one JSON handler across warm invocations and disables propagation. Free-form
messages are suppressed instead of being copied into the structured stream. Repository tests
cover lifecycle ordering, pagination telemetry, failure sanitization, and warm-handler
idempotency.

### 3.2 Bounded CC0 batch evidence

The validated portfolio DAG starts from already generated CC0-backed Bronze demo payloads. Its
run report therefore uses `source_type=cc0_demo` and `temporal_state=synthetic`.
`records_extracted` on this path means the item count present in the generated Bronze source
payload for that physical run. It is **not** evidence that Lambda fetched those rows from the
Spotify Web API.

---

## 4. Evidence Chain by Stage

| Evidence | Producer | What it proves | Mutability model |
| --- | --- | --- | --- |
| `plan.json` | Airflow `prepare` | Date window, provenance, physical IDs, source files, Bronze keys. | Run-scoped local artifact. |
| Bronze object | Airflow upload | Exact bytes selected by the plan reached the physical Bronze key. | Conditional create; existing bytes must match on retry. |
| `metadata/curation/<pipeline_run_id>/submission.json` | Airflow Glue submit | A physical run claimed a Glue submission before `StartJobRun`. | S3 `IfNoneMatch="*"`. |
| `glue-<pipeline_run_id>.json` | Airflow Glue submit | Glue job name/run ID associated with the physical record. | Run-scoped local artifact. |
| `metadata/curation/<pipeline_run_id>/complete.json` | Glue 5.1 | Six Silver file inventories, per-file rows, lineage, rejected count. | Published only after successful curation/inventory. |
| `landing-<pipeline_run_id>.json` | Airflow Landing sensor | Exact file/row readiness plus Glue execution metadata. | Run-scoped local artifact. |
| `dbt-summary.json` | Airflow dbt task | Successful/pass dbt node count and dbt elapsed time. | Derived from run-scoped `run_results.json`. |
| `run-summary.json` | Airflow final report task | Overall DAG status and run timestamps. | Final run-scoped summary. |
| `pipeline-run-report.json` | Reporting utility | Schema-validated aggregation of the evidence above. | Atomic local replace; optional immutable S3 publication. |

The optional S3 report path is
`s3://<bucket>/metadata/pipeline_runs/<run_key>.json`. Publication uses
`IfNoneMatch="*"`; a second upload for the same run key fails instead of silently mutating
historical evidence.

---

## 5. Exact Landing Gate

Snowflake readiness is intentionally stronger than “Snowpipe loaded something.” dbt runs only
after the physical files declared by Glue have been reconciled against Landing.

For every one of the six required datasets — `artists`, `albums`, `tracks`,
`track_artists`, `playlist_snapshots`, and `playlist_observations` — the gate checks:

1. the Glue completion manifest has the expected schema and matching
   `pipeline_run_id`/playlist/date lineage;
2. the completion manifest inventories at least one Parquet file per dataset and records each
   file's expected row count;
3. physical S3 paths stay inside the expected dataset/date/run/playlist prefix;
4. the bounded demo has exactly one playlist observation and zero rejected source items;
5. Snowflake rows belong to the exact run-scoped filenames declared by Glue;
6. `COUNT(*)` matches `COUNT(DISTINCT _FILE_ROW_NUMBER)`, preventing duplicate physical
   rows from passing;
7. observed row totals equal the Glue-declared row totals; unexpected, repeated, or excess
   files fail closed, while missing positive-row files keep the sensor waiting.

Zero-row Parquet inventory is handled explicitly: Glue can prove an expected dataset file has
zero rows without requiring a fabricated Landing row.

> [!TIP]
> `scripts/audit_landing_lag.py --dry-run` prints the bounded `COPY_HISTORY` queries without
> connecting to Snowflake. The audit is diagnostic; it does not bypass the exact readiness gate.

---

## 6. Unified `pipeline-run-report.json` — Schema v1

`src/spotify_data_platform/orchestration/reporting.py` is the schema authority. The utility
validates the report before local persistence and again before optional S3 publication.

### 6.1 Top-level fields

| Field | Type | Meaning |
| --- | --- | --- |
| `schema_version` | integer | Currently `1`. |
| `generated_at` | ISO-8601 timestamp | UTC report-generation time. |
| `run_key` | string | Storage-safe key derived from the Airflow run ID. |
| `airflow_run_id` | string | Original Airflow run identifier. |
| `status` | string | `success` or `failed`, sourced from `run-summary.json`. |
| `source_type` | string/null | Current bounded portfolio path reports `cc0_demo`. |
| `temporal_state` | string/null | Current bounded portfolio path reports `synthetic`. |
| `start_date` / `end_date` | date | Requested logical snapshot window. |
| `component_durations_seconds.airflow_total` | number/null | Run-summary finish minus start. |
| `component_durations_seconds.glue_total` | number/null | Sum of available Glue `ExecutionTime` values across physical runs. |
| `component_durations_seconds.dbt` | number/null | dbt elapsed time when a dbt summary exists. |
| `dbt_nodes_passed` | integer/null | Count of dbt results with successful/pass status. |
| `physical_runs` | array | One entry per persisted Landing evidence file. |

### 6.2 `physical_runs[]`

| Field | Type | Meaning |
| --- | --- | --- |
| `pipeline_run_id` | string | Physical curation/publication identifier. |
| `spotify_snapshot_id` | string/null | Live upstream or explicitly simulated demo source version. |
| `snapshot_date` | date | Logical observation date. |
| `playlist_id` | string | Playlist identity. |
| `records_extracted` | integer/null | Source input count; CC0 means generated Bronze item count. |
| `glue_job_run_id` | string/null | AWS Glue execution ID. |
| `glue_execution_time_seconds` | number/null | Glue `ExecutionTime` captured with Landing evidence. |
| `glue_dpu_seconds` | number/null | Glue `DPUSeconds` captured for that job run when available. |
| `landing_ready` | boolean | Whether every exact Landing dataset check passed. |
| `rejected_items` | integer | Rejected-item count from the Glue completion manifest. |
| `records_curated_by_dataset` | object | Expected Silver rows from the completion inventory for all six datasets. |
| `records_loaded_by_dataset` | object | Exact expected count when that Landing dataset is proven ready; otherwise `null`. |

The schema validator requires all six curated/Landing dataset keys. It intentionally does not
convert missing evidence into zero.

---

## 7. Airflow Failure and Deadline Events

The orchestration layer uses Airflow 3 Task SDK reliability primitives and emits structured
failure evidence independently from the batch report.

| Control | v1.0.0 behavior |
| --- | --- |
| Safe task retry | Three retries, five-minute initial delay, exponential backoff by default. |
| Glue submit | `retries=0`; ambiguous external submission is investigated before a new physical run. |
| Glue sensor | Reschedule mode, 30-second interval, one-hour timeout. |
| Landing sensor | Reschedule mode, 30-second interval, 15-minute timeout. |
| DAG timeout | Two hours. |
| Deadline Alert | Two hours from `DAGRUN_QUEUED_AT`. |
| Failure callback | Emits `DAG_FAILED`. |
| Deadline callback | Emits `DAG_DEADLINE_MISSED`. |

Both Airflow callback events are compact JSON records with safe context: timestamp, component,
status, DAG/task/run IDs, try number, and exception **type** when available. Exception message
text and credentials are not serialized into the event.

A Deadline Alert is an investigation signal, not proof that every task failed. Likewise, a
structured callback event is application evidence; this document does not claim a deployed
CloudWatch alarm, notification subscription, or observability dashboard.

---

## 8. Operator Commands

Generate the report for the latest completed local Airflow artifact directory:

```bash
.venv/bin/python scripts/generate_run_report.py
```

Select a specific run when comparing attempts:

```bash
.venv/bin/python scripts/generate_run_report.py --run-key '<run-key>' --json
```

or by original Airflow run ID:

```bash
.venv/bin/python scripts/generate_run_report.py \
  --airflow-run-id 'manual__example' \
  --json
```

Publish only when immutable remote evidence is desired:

```bash
export SPOTIFY_LAKE_BUCKET='<lake-bucket-name>'
.venv/bin/python scripts/generate_run_report.py --upload-s3
```

For recovery and replay, follow [`RUNBOOK.md`](RUNBOOK.md); do not bypass the exact Landing
gate with an ad-hoc load.

---

## 9. v1.0.0 Evidence Boundary

| Surface | What can be claimed |
| --- | --- |
| Spotify Lambda | Structured extraction lifecycle, source-version protection, auth/error handling, and sanitization are implemented/contract-tested. The bounded public demo does not prove live Spotify extraction. |
| Airflow 3 | Task SDK orchestration, safe retries, non-retried Glue submit, sensors, Deadline Alert, structured failure callbacks, and run artifacts are implemented. |
| Glue 5.1 | Completion manifests, run-scoped Silver inventories, and execution metadata feed the evidence chain. |
| Snowflake Landing | Exact run-scoped file and row readiness blocks dbt until the physical load is complete. |
| dbt | `run_results.json` is reduced to a run-scoped success/pass count and elapsed time; model/test semantics remain in the dbt project. |
| Unified reporting | Schema-v1 local report generation and optional immutable S3 publication are implemented. |
| CloudWatch/Grafana/APM dashboards | No dashboard or alert-delivery claim is made by this document. |
| Power BI | No dashboard validation claim is made by this document. |

The operating principle is simple: **claim only what a run artifact, contract test, or measured
execution can prove**.
