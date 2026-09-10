# Observability & Pipeline Telemetry

This document defines the observability framework, structured logging schema, audit mechanisms, and cross-tier monitoring strategy for the Spotify Analytics Data Platform.

---

## 1. Observability Strategy

The platform applies structured telemetry anchored by two distinct identifiers:
1. **`pipeline_run_id` (UUID v4)**: A non-deterministic physical execution identifier generated per pipeline run to track processing lineage across Lambda, Glue, Snowflake, and dbt.
2. **`spotify_snapshot_id` (String)**: An upstream version identifier emitted directly by Spotify representing the state of the playlist. It enables upstream mutation detection and idempotency verification.

M1 implements the core per-playlist execution fields as the Pydantic
`PipelineRunMetadata` contract in `spotify_data_platform.ingestion`. The complete
cross-tier event schema below adds component/version/duration metrics that are populated
by later cloud and observability milestones. Core telemetry is not injected into the
immutable Bronze source snapshot JSON.

---

## 2. Standard Telemetry Event Schema

All pipeline components emit JSON-structured log events adhering to the following schema:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "PipelineExecutionTelemetry",
  "type": "object",
  "required": [
    "pipeline_run_id",
    "source",
    "playlist_id",
    "spotify_snapshot_id",
    "snapshot_date",
    "snapshot_timestamp",
    "pipeline_version",
    "status"
  ],
  "properties": {
    "pipeline_run_id": { "type": "string", "format": "uuid" },
    "source": { "type": "string", "example": "spotify_web_api" },
    "playlist_id": { "type": "string" },
    "spotify_snapshot_id": { "type": "string" },
    "snapshot_date": { "type": "string", "format": "date" },
    "snapshot_timestamp": { "type": "string", "format": "date-time" },
    "pipeline_version": { "type": "string", "example": "0.1.1" },
    "records_extracted": { "type": "integer", "minimum": 0 },
    "records_validated": { "type": "integer", "minimum": 0 },
    "records_written_raw": { "type": "integer", "minimum": 0 },
    "records_written_curated": { "type": "integer", "minimum": 0 },
    "records_loaded_snowflake": { "type": "integer", "minimum": 0 },
    "records_rejected": { "type": "integer", "minimum": 0 },
    "lambda_duration_sec": { "type": "number", "minimum": 0 },
    "glue_duration_sec": { "type": "number", "minimum": 0 },
    "dbt_duration_sec": { "type": "number", "minimum": 0 },
    "total_pipeline_duration_sec": { "type": "number", "minimum": 0 },
    "status": { "type": "string", "enum": ["RUNNING", "SUCCESS", "FAILED", "PARTIAL"] },
    "error_message": { "type": ["string", "null"] }
  }
}
```

---

## 3. Component Logging Channels

| Component | Destination | Format | Key Metrics Logged |
| :--- | :--- | :--- | :--- |
| **AWS Lambda** | Amazon CloudWatch Logs (`/aws/lambda/spotify-extractor`) | JSON | API response codes, pagination counts, latency, `spotify_snapshot_id`, S3 PutObject status |
| **AWS Glue 5.1** | Amazon CloudWatch Logs (`/aws-glue/jobs/spotify-silver-transformation`) | JSON / Text | Input row counts, schema validation errors, items exploded, output Parquet partitions |
| **Snowpipe** | Snowflake Ingestion History (`SNOWFLAKE.ACCOUNT_USAGE.COPY_HISTORY`) | SQL Table | Files loaded, rows parsed, byte sizes, parse error counts |
| **dbt Core** | dbt Artifacts (`target/run_results.json`, `target/manifest.json`) | JSON | Model build durations, rows merged, test assertion pass/fail counts |
| **Apache Airflow 3**| Airflow Task Logs (`airflow/logs/`) | Text / Structured | Task lifecycle events, Deadline Alerts, sensor evaluation intervals |

---

## 4. Operational Auditing & Quality Verification

### Snowflake Landing Verification Query
Verify that Snowpipe successfully loaded the Parquet files produced by Glue:

```sql
SELECT
    TABLE_NAME,
    ROW_COUNT,
    LAST_ALTERED
FROM SPOTIFY_ANALYTICS.INFORMATION_SCHEMA.TABLES
WHERE TABLE_SCHEMA = 'LANDING'
ORDER BY TABLE_NAME;
```

### Snowpipe Ingestion Status Query
```sql
SELECT
    PIPE_NAME,
    FILE_NAME,
    STATUS,
    ROW_COUNT,
    ERROR_MESSAGE,
    LAST_LOAD_TIME
FROM TABLE(INFORMATION_SCHEMA.COPY_HISTORY(
    TABLE_NAME=>'SPOTIFY_ANALYTICS.LANDING.LANDING_TRACKS',
    START_TIME=>DATEADD(hours, -2, CURRENT_TIMESTAMP())
));
```

---

## 5. Cost-Conscious Monitoring Design

- **No Paid Third-Party Observability Tools**: Avoid Datadog, New Relic, or commercial APM subscriptions.
- **CloudWatch Retention**: Capped at **7 days** to eliminate log storage accumulation costs.
- **Basic Metric Alarms**: Single CloudWatch alarm triggering on Lambda error count > 0.
