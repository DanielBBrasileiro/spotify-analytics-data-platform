# Observability & Pipeline Telemetry

This document separates the **implemented M2 Lambda telemetry contract** from future
cross-tier observability. The repository currently validates logging offline; it does
not provision or claim a live CloudWatch deployment.

---

## 1. Correlation Model

Two identifiers remain intentionally distinct:

1. **`pipeline_run_id` (UUID v4)** identifies one physical execution and is supplied
   by the invocation contract.
2. **`spotify_snapshot_id`** identifies the upstream playlist version once playlist
   metadata has established it. The key is present on every Lambda lifecycle event,
   but its value is `null` before that point instead of inventing a source version.

`snapshot_date` is the logical business observation date. Event `timestamp` is the
UTC time at which a log record is emitted. `snapshot_timestamp` belongs to the
successful observation metadata and is included on `EXTRACTION_COMPLETE`; it is not a
required field on events emitted before a successful capture exists.

Core run metadata remains separate from raw Bronze JSON; telemetry is never injected
into source payloads.

---

## 2. Implemented Lambda Event Schema

Every structured Lambda event contains these fields:

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
| `spotify_snapshot_id` | String once known, otherwise `null`. |
| `snapshot_date` | Logical observation date (`YYYY-MM-DD`). |
| `duration_ms` | Non-negative elapsed duration for the event scope. |
| `status` | `RUNNING`, `SUCCESS`, or `FAILED`. |

Event-specific scalar fields may be added, but cannot overwrite the correlation
fields above.

### Lifecycle Events

| Event | Additional fields | Semantics |
| --- | --- | --- |
| `EXTRACTION_START` | none | Playlist processing started; source version may be unknown. |
| `PAGINATION_PAGE_FETCHED` | `page_number`, `offset`, `records_in_page`, `total_records` | Emitted only after pagination validation and a matching source-version check. |
| `S3_WRITE_SUCCESS` | `records_extracted`, `s3_uri` | Immutable conditional Bronze publication succeeded. |
| `EXTRACTION_COMPLETE` | `records_extracted`, `snapshot_timestamp` | Playlist extraction and Bronze landing completed successfully. |
| `EXTRACTION_FAILED` | `error_type` | Failure record contains only the exception class name, never exception text/body. |

`JsonLogFormatter` serializes telemetry as compact single-line JSON. The dedicated
Lambda logger owns exactly one JSON stream handler across warm invocations and disables
propagation. If an unstructured record reaches that logger, its free-form message is
suppressed rather than copied into the JSON output.

---

## 3. Current Coverage Boundary

Issue #8 instruments playlist processing after the event, non-secret bucket setting,
credential provider, and logger runtime have been constructed. Validation/configuration
failures that occur before the `LambdaExtractorService` starts do not yet emit a
run-level failure event.

The offline suite verifies lifecycle ordering, page telemetry, failure sanitization,
single-line JSON, warm-handler idempotency, and zero additional service timing calls
when telemetry is not configured. Network and DNS are blocked during tests.

---

## 4. CloudWatch Deployment Boundary

Managed AWS Lambda captures application logging streams into CloudWatch Logs when the
function is deployed with the corresponding execution permissions/configuration. M2
only implements the application-side JSON logging contract.

The following remain unprovisioned and belong to later infrastructure/observability
work:

- CloudWatch log-group retention policy;
- metric filters and alarms;
- dashboards or third-party APM;
- Glue structured telemetry;
- Airflow task/event correlation;
- Snowflake load-history monitoring;
- dbt artifacts and cross-tier quality metrics.

No live CloudWatch log delivery has been validated by the current test suite.

---

## 5. Future Cross-Tier Observability

M7 extends the Lambda correlation model across Glue, Snowflake, dbt, and Airflow. The
future schema may add records validated/written/loaded/rejected, per-tier durations,
warehouse load metadata, and explicit failure-event contracts for stages where a
Spotify source version does not exist.

Snowflake auditing queries and CloudWatch alarms should be added only after their
corresponding resources exist and can be integration-tested; documentation must not
present illustrative queries or cost controls as deployed behavior.
