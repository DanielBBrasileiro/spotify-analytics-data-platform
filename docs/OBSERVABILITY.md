# Observability & Pipeline Evidence

This project treats observability as an evidence chain rather than a dashboard claim.
The live Spotify extractor emits structured Lambda lifecycle events, while the current
portfolio DAG persists Airflow, Glue, Snowflake Landing, and dbt evidence that can be
consolidated into one `pipeline-run-report.json`.

The two paths are intentionally explicit about their boundary: the portfolio DAG uses the
CC0-backed demo source, so the unified batch report does not imply that live Spotify Lambda
extraction happened. Live Spotify extraction telemetry remains a separate source-side contract
until that path is exercised end to end.

---

## 1. Correlation Model

Several identifiers appear in the evidence because they answer different questions:

| Identifier | Meaning | Stability |
| --- | --- | --- |
| `airflow_run_id` | One Airflow DAG run, including a bounded date window. | Assigned by Airflow. |
| `run_key` | Filesystem/S3-safe SHA-256-derived key for the `airflow_run_id`. | Deterministic for one Airflow run. |
| `pipeline_run_id` | One physical playlist/date curation attempt and its immutable Bronze/Silver paths. | Fresh for a new Airflow run; stable across task retries in that run. |
| `spotify_snapshot_id` | Upstream playlist source version captured from Spotify metadata, or the explicitly simulated source version in the CC0 demo. | Source-version identity, not an execution ID. |
| `snapshot_date` | Logical business observation date (`YYYY-MM-DD`). | Logical data grain. |

`pipeline_run_id` and `spotify_snapshot_id` must never be conflated. A replay creates a
fresh physical execution while preserving the logical snapshot date and source provenance.
That allows the system to prove which physical files were produced without changing the
canonical analytical grain.

For the CC0 portfolio path, `source_type=cc0_demo` and `temporal_state=synthetic` are
carried from the plan into the unified report. The source metadata is real CC0-licensed
catalog data; the multi-day playlist evolution is intentionally synthetic.

---

## 2. Lambda Structured Telemetry Contract

The Spotify Lambda extractor emits compact, single-line JSON events. Every event contains:

| Field | Contract |
| --- | --- |
| `timestamp` | UTC ISO-8601 event emission time. |
| `event` | Stable lifecycle event name. |
| `level` | `INFO` or `ERROR`. |
| `source` | `spotify_web_api`. |
| `component` | `lambda`. |
| `pipeline_version` | Repository package version. |
| `pipeline_run_id` | UUID v4 physical execution identifier. |
| `playlist_id` | 22-character playlist identifier. |
| `spotify_snapshot_id` | Source version once known, otherwise `null`. |
| `snapshot_date` | Logical observation date. |
| `duration_ms` | Non-negative elapsed duration for the event scope. |
| `status` | `RUNNING`, `SUCCESS`, or `FAILED`. |

Lifecycle events add only scalar fields and cannot overwrite the correlation fields above.

| Event | Additional fields | Meaning |
| --- | --- | --- |
| `EXTRACTION_START` | none | Playlist processing started; source version may still be unknown. |
| `PAGINATION_PAGE_FETCHED` | `page_number`, `offset`, `records_in_page`, `total_records` | A validated page was received while the source version still matched. |
| `S3_WRITE_SUCCESS` | `records_extracted`, `s3_uri` | Immutable Bronze publication succeeded. |
| `EXTRACTION_COMPLETE` | `records_extracted`, `snapshot_timestamp` | Source extraction and Bronze landing completed. |
| `EXTRACTION_FAILED` | `error_type` | Sanitized failure event containing the exception class, never the exception body. |

The Lambda logger owns one JSON handler across warm invocations and disables propagation.
Free-form records are suppressed rather than copied into structured output. Repository tests
cover event ordering, pagination telemetry, sanitization, warm-handler idempotency, and the
absence of secret/error-body leakage.

For live source telemetry, `records_extracted` means records fetched by Lambda. In the CC0
Airflow report the same field is explicitly source-scoped: it is the item count already present
in the generated Bronze demo payload. `source_type=cc0_demo` and `temporal_state=synthetic`
prevent that count from being presented as a live Spotify Lambda extraction.

---

## 3. Batch Evidence Chain

The Airflow 3 Task SDK DAG persists small JSON evidence files under one run directory before
the unified report is generated. These files are operational evidence, not source payloads.

| Evidence | Producer | What it proves |
| --- | --- | --- |
| `plan.json` | Airflow `prepare` task | Requested date window, source/temporal provenance, immutable physical IDs and Bronze keys. |
| `glue-<pipeline_run_id>.json` | Airflow Glue submission task | Exact Glue job name/run ID associated with one physical record. |
| `metadata/curation/<pipeline_run_id>/complete.json` | Glue 5.1 job in S3 | Run-scoped Silver file inventory, per-file row counts, lineage fields, and rejected item count. |
| `landing-<pipeline_run_id>.json` | Airflow Landing sensor | Exact Snowflake Landing readiness for the files declared by Glue, plus the Glue completion manifest. |
| `dbt-summary.json` | Airflow dbt task | Number of successful/pass nodes and dbt elapsed time derived from `run_results.json`. |
| `run-summary.json` | Airflow report task | Overall DAG outcome and start/finish timestamps. |
| `pipeline-run-report.json` | `scripts/generate_run_report.py` | Schema-validated aggregation of the evidence above. |

Landing readiness is deliberately stricter than “some rows arrived.” For every Silver dataset,
the sensor compares exact run-scoped filenames, expected row totals, and distinct Snowflake
file-row numbers. Unexpected files, duplicate rows, excess rows, missing positive-row files,
or rejected source items fail closed before dbt runs.

---

## 4. Unified `pipeline-run-report.json` Schema (v1)

`src/spotify_data_platform/orchestration/reporting.py` is the schema authority. The report is
validated before local persistence and again before optional S3 upload.

### Top-level fields

| Field | Type | Meaning |
| --- | --- | --- |
| `schema_version` | integer | Currently `1`. |
| `generated_at` | ISO-8601 timestamp | UTC report-generation time. |
| `run_key` | string | Safe key derived from the Airflow run ID. |
| `airflow_run_id` | string | Original Airflow run identifier. |
| `status` | string | `success` or `failed`, sourced from `run-summary.json`. |
| `source_type` | string/null | Current portfolio path reports `cc0_demo`. |
| `temporal_state` | string/null | Current portfolio path reports `synthetic`. |
| `start_date` | date | First requested logical snapshot date. |
| `end_date` | date | Last requested logical snapshot date. |
| `component_durations_seconds.airflow_total` | number/null | Difference between run-summary start and finish timestamps. |
| `component_durations_seconds.dbt` | number/null | dbt elapsed time when `dbt-summary.json` exists. |
| `dbt_nodes_passed` | integer/null | Successful/pass dbt result count when available. |
| `physical_runs` | array | One entry per run-scoped Landing evidence file. |

### `physical_runs[]` fields

| Field | Type | Meaning |
| --- | --- | --- |
| `pipeline_run_id` | string | Physical curation/publication identifier. |
| `spotify_snapshot_id` | string/null | Upstream or simulated source version carried by the Glue record. |
| `snapshot_date` | date | Logical observation date. |
| `playlist_id` | string | Playlist identity. |
| `records_extracted` | integer/null | Source input count for the physical run. For `cc0_demo`, this is the generated Bronze item count, not evidence of live Lambda extraction. |
| `glue_job_run_id` | string/null | Glue execution ID from Airflow/landing evidence. |
| `landing_ready` | boolean | Whether all exact Landing checks passed. |
| `rejected_items` | integer | Count from Glue completion metadata. |
| `records_curated_by_dataset` | object | Expected Silver rows for all six datasets, summed from the Glue completion inventory. |
| `records_loaded_by_dataset` | object | The same exact expected count when Landing readiness for that dataset is proven; otherwise `null`. |

The six required curated/Landing datasets are `artists`, `albums`, `tracks`,
`track_artists`, `playlist_snapshots`, and `playlist_observations`. Schema validation rejects
reports that omit one of these datasets.

Illustrative shape:

```json
{
  "schema_version": 1,
  "generated_at": "2026-09-15T20:00:00+00:00",
  "run_key": "<sha256-derived-run-key>",
  "airflow_run_id": "manual__example",
  "status": "success",
  "source_type": "cc0_demo",
  "temporal_state": "synthetic",
  "start_date": "2026-09-10",
  "end_date": "2026-09-10",
  "component_durations_seconds": {
    "airflow_total": 180.0,
    "dbt": 82.5
  },
  "dbt_nodes_passed": 152,
  "physical_runs": [
    {
      "pipeline_run_id": "<uuid-v4>",
      "spotify_snapshot_id": "<source-version>",
      "snapshot_date": "2026-09-10",
      "playlist_id": "<playlist-id>",
      "glue_job_run_id": "<glue-run-id>",
      "landing_ready": true,
      "rejected_items": 0,
      "records_curated_by_dataset": {
        "artists": 12,
        "albums": 12,
        "tracks": 12,
        "track_artists": 12,
        "playlist_snapshots": 12,
        "playlist_observations": 1
      },
      "records_loaded_by_dataset": {
        "artists": 12,
        "albums": 12,
        "tracks": 12,
        "track_artists": 12,
        "playlist_snapshots": 12,
        "playlist_observations": 1
      }
    }
  ]
}
```

The values above demonstrate the schema only; they are not presented as a production run.

---

## 5. Generating and Publishing a Run Report

Generate the report for the latest completed local Airflow artifact directory:

```bash
.venv/bin/python scripts/generate_run_report.py
```

Inspect a specific run without relying on “latest” selection:

```bash
.venv/bin/python scripts/generate_run_report.py \
  --run-key '<run-key>' \
  --json
```

Or select by the original Airflow run ID:

```bash
.venv/bin/python scripts/generate_run_report.py \
  --airflow-run-id 'manual__example' \
  --json
```

S3 publication is explicit:

```bash
export SPOTIFY_LAKE_BUCKET='<lake-bucket-name>'
.venv/bin/python scripts/generate_run_report.py --upload-s3
```

The remote key is `metadata/pipeline_runs/<run_key>.json`. Upload uses `IfNoneMatch="*"`, so
an existing report cannot be silently overwritten. Re-generating locally is safe; publishing
the same `run_key` twice fails instead of mutating historical evidence.

---

## 6. Airflow Failure and Deadline Evidence

The orchestration path uses Airflow 3 Task SDK primitives. The DAG currently has:

- three default task retries with a five-minute initial delay and exponential backoff;
- bounded task/sensor execution timeouts;
- a two-hour DAG-run timeout;
- an Airflow 3 `DeadlineAlert` referenced to `DAGRUN_QUEUED_AT` with a two-hour interval;
- structured `DAG_FAILED` and `DAG_DEADLINE_MISSED` callbacks.

Deadline Alerts replace the removed legacy SLA mechanism; the repository does not use legacy
`sla=` syntax. Callback payloads contain safe execution context such as DAG/task/run IDs,
try number, and exception class only. They do not serialize exception messages or credentials.

---

## 7. Validation Boundary

The repository has strong offline contracts around telemetry/report construction and a bounded
CC0 portfolio path for the batch stack. The evidence should be described precisely:

| Layer | Current evidence boundary |
| --- | --- |
| Spotify Lambda | Structured lifecycle contract and extraction/auth behavior are validated by repository tests. Live Spotify extraction is a separate source-side gate and is not claimed by the CC0 run report. |
| Glue 5.1 | Completion manifests and physical Silver inventories are part of the Airflow evidence chain; the portfolio uses the Glue 5.1 / Spark 3.5.6 contract. |
| Snowflake Landing | Exact file/row readiness is checked before dbt; `audit_landing_lag.py` offers a separate read-only COPY-history inspection path. |
| dbt | `dbt build` result metadata is summarized from `run_results.json`; models/tests remain the business-quality gate after Landing readiness. |
| Airflow 3 | Task SDK DAG, retries, sensors, failure callback, Deadline Alert, per-run artifacts, and run summary form the orchestration evidence. |
| Power BI | No validation claim is made here. Serving marts may be consumed by BI only after their own connection/dashboard verification. |

CloudWatch log-group retention, metric filters, dashboards, and third-party APM are not implied
by this document. Application telemetry and run evidence can exist without claiming that those
managed observability resources were deployed or validated.
