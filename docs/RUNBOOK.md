# Operational Runbook & Incident Response

This runbook provides actionable remediation procedures and recovery playbooks for common operational failure scenarios across the Spotify Analytics Data Platform.

---

## 1. Quick Triage Flowchart

```
Pipeline Failure Alert
       │
       ▼
Identify Failing Layer:
├── A. Authentication & Ingestion ──> See Section 2: Spotify Auth & Lambda Extractor
├── B. AWS Glue 5.1 ETL Failure   ──> See Section 3: Lake Processing & Schemas
├── C. Snowpipe Ingestion Lag     ──> See Section 4: Snowflake Ingestion
└── D. dbt Test Failure           ──> See Section 5: Data Quality Assertions
```

---

## 2. Playbook A: Spotify Auth & Lambda Ingestion Failures

### Symptoms
- Airflow `extract_spotify_raw` task fails with exit code or timeout.
- CloudWatch logs show `invalid_grant`, HTTP `429 Too Many Requests`, or `500 Internal Server Error`.

### Remediation Steps
1. **Handle Token Expiration / Revocation (`invalid_grant`)**:
   - If the refresh token was revoked by the user or invalidated:
     1. Run the local setup utility to perform a one-time interactive re-authorization.
     2. Update the secret in AWS Secrets Manager:
        ```bash
        aws secretsmanager put-secret-value \
            --secret-id spotify/api/credentials \
            --secret-string '{"client_id":"...","client_secret":"...","refresh_token":"NEW_TOKEN"}'
        ```
     3. Re-trigger the failed Airflow DAG run.
2. **Handle Rate Limiting (HTTP 429)**:
   - Ensure the client respects the `Retry-After` response header.
   - If Spotify is throttling requests due to quota saturation, delay execution by 1 hour or adjust Airflow schedule cadence.
3. **Mid-Pagination Snapshot ID Drift**:
   - If CloudWatch logs show `SnapshotIdMismatchException`, the monitored playlist was updated while extraction was underway. The extractor aborts to preserve atomicity; re-triggering the task will fetch the new atomic snapshot.

---

## 3. Playbook B: AWS Glue 5.1 / Spark Transformation Failures

### Symptoms
- Airflow `wait_for_glue` sensor times out or reports `FAILED`.
- Glue CloudWatch logs indicate `AnalysisException`, `SchemaMismatch`, or `OutOfMemoryError`.

### Remediation Steps
1. **Analyze Failed Spark Task**:
   - Inspect CloudWatch logs under `/aws-glue/jobs/spotify-silver-transformation-job`.
2. **Handle Schema Mismatch / Non-Track Items**:
   - If an unexpected item type entered the playlist, verify whether it was correctly routed to quarantine.
   - Adjust `glue/schemas/bronze_schema.py` or item filtering logic if a supported field structure changed.
3. **Re-Run Partition Transformation**:
   - Re-execute the Glue job for the specific partition:
     ```bash
     aws glue start-job-run \
         --job-name spotify-silver-transformation-job \
         --arguments '{"--snapshot_date": "YYYY-MM-DD", "--pipeline_run_id": "manual-recovery"}'
     ```

---

## 4. Playbook C: Snowpipe Ingestion Lag or Stalled Copies

### Symptoms
- AWS Glue finished successfully, but Snowflake `LANDING` tables show 0 rows for the target date.
- Downstream Airflow row count validation fails.

### Remediation Steps
1. **Check Snowpipe Status**:
   ```sql
   SELECT SYSTEM$PIPE_STATUS('SPOTIFY_ANALYTICS.LANDING.PIPE_LANDING_TRACKS');
   ```
   - Look for `executionState: RUNNING` and `pendingFileCount`.
2. **Inspect SQS & Load Errors**:
   ```sql
   SELECT * FROM TABLE(VALIDATE_PIPE_LOAD(
       PIPE_NAME => 'SPOTIFY_ANALYTICS.LANDING.PIPE_LANDING_TRACKS',
       START_TIME => DATEADD(HOUR, -2, CURRENT_TIMESTAMP())
   ));
   ```
3. **Manual Fallback COPY**:
   - If Snowpipe notification stalled, execute manual copy:
     ```sql
     COPY INTO SPOTIFY_ANALYTICS.LANDING.LANDING_TRACKS
     FROM @SPOTIFY_ANALYTICS.LANDING.STAGE_SILVER_PARQUET/tracks/ingestion_date=YYYY-MM-DD/
     FILE_FORMAT = (FORMAT_NAME = 'SPOTIFY_ANALYTICS.LANDING.PARQUET_FORMAT');
     ```

---

## 5. Playbook D: dbt Test Assertion Failure

### Symptoms
- `dbt test` or `dbt build` halts with failure in Airflow.
- Terminal output indicates assertion failure on `unique`, `not_null`, or `relationships`.

### Remediation Steps
1. **Locate Failing Test Query**:
   - Inspect compiled SQL query in `dbt/target/compiled/...`.
2. **Execute Query in Snowflake**:
   - Run the compiled test query to identify offending rows.
   - Common causes:
     - Unexpected NULL in `track_id` from local or deleted Spotify items.
     - Duplicate positions resulting from unmerged historical files.
3. **Remediate**:
   - Update staging model logic in `dbt/models/staging/` to filter or coalesce anomalies, re-run `dbt build`.

---

## 6. Backfill & Replay Procedure

To backfill historical dates:

1. Identify target date range: `START_DATE` to `END_DATE`.
2. Verify raw JSON exists in `s3://<bucket>/bronze/spotify/playlist_tracks/` for those dates.
3. Trigger Airflow backfill DAG:
   ```bash
   airflow dags backfill \
       --start-date YYYY-MM-DD \
       --end-date YYYY-MM-DD \
       spotify_daily_snapshot_dag
   ```
4. dbt executes `incremental_strategy = 'merge'` on `snapshot_pk`, updating existing records or appending missing dates deterministically.
