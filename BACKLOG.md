# Project Backlog & Implementation Roadmap

This backlog establishes the structured, phased implementation roadmap for the **Spotify Analytics Data Platform**. Each milestone maps to an engineering sprint containing atomic, reviewable implementation issues aligned with the 2026 Spotify Web API, AWS Glue 5.1, and Apache Airflow 3.x specifications.

---

## Milestone Summary

| Milestone | Title | Status | Target Scope |
| :--- | :--- | :--- | :--- |
| **M0** | **Project Foundation & Architecture Blueprint** | **COMPLETED (v0.1.1)** | Repository bootstrapping, architecture blueprint, ADRs, cost governance, CI |
| **M1** | **Local Spotify Ingestion** | **COMPLETED** | Auth Code + refresh-token client, `/items` pagination (limit=50), snapshot_id, fixtures, run metadata, local Bronze persistence |
| **M2** | **AWS Lambda & Bronze Data Lake** | **COMPLETED** | Serverless extractor runtime, immutable S3 Bronze contract, Secrets Manager credential provider, structured Lambda telemetry |
| **M3** | **Glue / PySpark & Silver Layer** | **COMPLETED (offline-validated)** | AWS Glue 5.1 parity (Spark 3.5.6 / Python 3.11), StructType schemas, item validation, Parquet Silver |
| **M4** | **Snowflake & Snowpipe** | **Contracts implemented; cloud validation pending** | Storage integration, external stage, Snowpipe auto-ingest, Landing tables with audit metadata |
| **M5** | **dbt Analytics Engineering** | Planned | Staging views, Kimball star schema, incremental merge fact model (`snapshot_pk`), marts |
| **M6** | **Airflow Orchestration** | Planned | Apache Airflow 3.x Task SDK, Deadline Alerts, external service operators, error handling |
| **M7** | **Data Quality & Observability** | Planned | Cross-tier quality gates, structured telemetry reporting (`run_id` & `snapshot_id`), runbooks |
| **M8** | **Terraform & CI/CD Hardening** | Planned | Terraform modules (S3, IAM, Lambda, Glue), CI security, AWS Budgets alert thresholds |
| **M9** | **Power BI & Portfolio Release** | Planned | Semantic model, DAX measures (churn, longevity), portfolio dashboard, interview showcase |

---

## Detailed Milestone Issues

### Milestone M1: Local Spotify Ingestion
- **#1 [M1] Implement Spotify API OAuth client and authentication abstraction**
  - *Context*: Modern Spotify Web API access requires OAuth 2.0 Authorization Code flow with user consent and token refresh (ADR-0007).
  - *Objective*: Build a robust Python authentication client that manages token refresh, in-memory caching, and expiration handling using a stored `refresh_token`.
- **#2 [M1] Implement paginated playlist items extractor**
  - *Context*: Playlist item inspection uses `GET /v1/playlists/{id}/items` with a maximum pagination limit of 50 items per request.
  - *Objective*: Build a pagination engine that retrieves all items, handles HTTP 429 rate limits, validates item types, and yields consolidated atomic snapshots.
- **#3 [M1] Add Spotify response fixtures and unit parser tests**
  - *Context*: Offline unit testing must validate API parsing without live network dependencies.
  - *Objective*: Create synthetic 2026 API fixtures (items, multi-artist tracks, nullable fields, rate limits, `spotify_snapshot_id`) and pytest parser suites.
- **#4 [M1] Define ingestion run metadata model and local persistence**
  - *Context*: Ingestion runs must attach standard telemetry (`pipeline_run_id` as non-deterministic execution UUID, `snapshot_date`, `spotify_snapshot_id`).
  - *Objective*: Implement Pydantic domain models validating run telemetry and landing raw JSON locally matching S3 Bronze layout.

### Milestone M2: AWS Lambda & Bronze Data Lake
- **#5 [M2] Define S3 Bronze object layout and naming convention**
  - *Status*: Completed in PR #45.
  - *Context*: Raw data lake storage must be partitioned deterministically for auditability (ADR-0002).
  - *Objective*: Formalize and implement S3 client utilities writing to `bronze/spotify/playlist_tracks/ingestion_date=YYYY-MM-DD/run_id=<id>/`.
- **#6 [M2] Implement AWS Lambda Spotify raw extractor handler**
  - *Status*: Completed in PR #46.
  - *Context*: Serverless execution decouples extraction from local machines.
  - *Objective*: Package the existing auth/extractor contracts into a lightweight AWS Lambda handler with immutable S3 Bronze publication. The `< 30s` target requires a future live benchmark; Secrets Manager retrieval remains Issue #7.
- **#7 [M2] Integrate AWS Secrets Manager for API credentials in Lambda**
  - *Status*: Completed in PR #47; credential-boundary hardening followed in PR #48.
  - *Context*: Secure credential management for `client_id`, `client_secret`, and `refresh_token`.
  - *Objective*: Fetch credentials dynamically from AWS Secrets Manager for cloud execution, cache them across warm invocations, and use environment credentials only for explicit local mode.
- **#8 [M2] Add CloudWatch structured JSON logging to Lambda**
  - *Status*: Completed in PR #49.
  - *Context*: Ingestion observability requires structured telemetry in log streams.
  - *Objective*: Configure Python logging to emit single-line JSON lifecycle events containing `pipeline_run_id`, playlist/source-version correlation, latency, and record counts. CloudWatch infrastructure/retention remains unprovisioned until M8.

### Milestone M3: Glue / PySpark & Silver Layer
- **Status**: Completed in PR #50; per-object lineage hardening followed in PR #51.
- **#9 [M3] Define explicit PySpark StructType schemas for Bronze & Silver**
  - *Context*: Schema inference causes performance penalties and permits silent drift.
  - *Objective*: Define strict PySpark `StructType` schemas for Bronze JSON items and Silver Parquet datasets for AWS Glue 5.1.
- **#10 [M3] Implement artists and albums normalization logic in PySpark**
  - *Context*: Artist and album metadata is nested within track items.
  - *Objective*: Build PySpark transformation logic extracting deduplicated artist and album entities.
- **#11 [M3] Implement tracks and track-artist bridge extraction**
  - *Context*: Tracks have many-to-many relationships with contributing artists.
  - *Objective*: Explode artist arrays to produce normalized `tracks` and `track_artists` bridge datasets.
- **#12 [M3] Implement historical playlist snapshot normalization & deduplication**
  - *Context*: Capturing point-in-time snapshot slots with `spotify_snapshot_id` and position metadata.
  - *Objective*: Transform raw playlist items into a point-in-time snapshot entity dataset.
- **#13 [M3] Write partitioned Parquet serialization and local PySpark tests**
  - *Context*: Silver data must be serialized efficiently and tested locally without AWS.
  - *Objective*: Implement Snappy-compressed Parquet output writing partitioned by date, with local pytest test suite on Spark 3.5.

### Milestone M4: Snowflake & Snowpipe
- **Status**: Version-controlled SQL/contracts implemented offline. No Snowflake objects,
  AWS IAM trust, S3 notifications, or live Snowpipe delivery have been provisioned yet.
- **#14 [M4] Define Snowflake databases, schemas, and RBAC roles**
  - *Status*: Implemented and statically validated offline; live account syntax/privilege verification pending.
  - *Context*: Warehouse architecture requires structured schemas and least-privilege security roles (ADR-0004).
  - *Objective*: Write DDL creating `LANDING`, `STAGING`, `CORE`, `MARTS` and dedicated roles (`SPOTIFY_LOADER`, `SPOTIFY_TRANSFORMER`, `SPOTIFY_ANALYST`).
- **#15 [M4] Configure AWS IAM storage integration and S3 external stage**
  - *Status*: DDL/trust-policy templates prepared; real IAM/Snowflake integration intentionally pending.
  - *Context*: Secure cross-account access between AWS S3 and Snowflake without static credentials.
  - *Objective*: Create Snowflake Storage Integration pointing to S3 Silver stage with IAM trust relationship.
- **#16 [M4] Implement Snowpipe auto-ingest for Silver Parquet**
  - *Status*: Five pipe definitions prepared; S3/SQS notification wiring and live delivery intentionally pending.
  - *Context*: Automated loading into Landing tables upon file arrival in S3.
  - *Objective*: Create Snowpipe definitions with `AUTO_INGEST = TRUE` mapped to SQS event notifications, capturing file audit metadata.
- **#17 [M4] Create Snowflake Landing tables and load validation queries**
  - *Status*: Landing DDL and offline validation contracts implemented; live load-history validation pending.
  - *Context*: Landing tables require exact 1:1 typing with Parquet schemas and audit verification.
  - *Objective*: Write DDL for Landing tables (including `landing_track_artists` and audit columns) and validation queries.

### Milestone M5: dbt Analytics Engineering
- **#18 [M5] Initialize dbt Core project with Snowflake adapter**
  - *Context*: Centralizing analytical transformations requires a version-controlled dbt project.
  - *Objective*: Scaffold dbt project (`dbt_project.yml`, profiles template, directory structure, packages).
- **#19 [M5] Build dbt staging models for Landing sources**
  - *Context*: Raw Landing tables require light cleansing, naming conventions, and item validation.
  - *Objective*: Create staging views `stg_spotify_artists`, `stg_spotify_albums`, `stg_spotify_tracks`, `stg_spotify_track_artists`, `stg_spotify_playlist_snapshots`.
- **#20 [M5] Build Kimball core dimensions and track-artist bridge**
  - *Context*: Star schema reporting requires clean dimensions and bridge relationships.
  - *Objective*: Implement `dim_track`, `dim_artist`, `dim_album`, `dim_playlist`, and `bridge_track_artist` using surrogate hashing.
- **#21 [M5] Build incremental fact_playlist_snapshot model**
  - *Context*: Snapshots must be merged incrementally on canonical grain `(playlist_id + snapshot_date + track_position)`.
  - *Objective*: Build incremental dbt model `fact_playlist_snapshot` with `incremental_strategy = 'merge'` on `snapshot_pk` supporting arbitrary backfills.
- **#22 [M5] Build analytical marts and dbt data quality tests**
  - *Context*: Business metrics (churn, retention, artist presence, position movement) serve BI dashboards.
  - *Objective*: Implement `mart_artist_presence`, `mart_playlist_trends`, `mart_track_lifecycle`, `mart_playlist_changes` and comprehensive dbt tests.

### Milestone M6: Airflow Orchestration
- **#23 [M6] Create local Docker Compose Airflow environment**
  - *Context*: Cost-effective orchestration testing requires containerized local Airflow.
  - *Objective*: Create `docker-compose.yml`, custom Dockerfile for Apache Airflow 3.x with AWS and Snowflake providers.
- **#24 [M6] Implement end-to-end daily orchestration DAG**
  - *Context*: Coordinating Lambda, Glue 5.1, Snowpipe, and dbt in a scheduled workflow.
  - *Objective*: Build `spotify_daily_snapshot_dag` using the Airflow 3 Task SDK (`airflow.sdk`).
- **#25 [M6] Add external execution operators (Lambda, Glue, Snowflake, dbt)**
  - *Context*: Enforcing Airflow as orchestrator requires external operator integration.
  - *Objective*: Configure operators for Lambda invocation, Glue 5.1 execution, Snowflake landing checks, and dbt run.
- **#26 [M6] Implement pipeline retries, SLA sensors, and failure alerts**
  - *Context*: Production pipelines must handle transient network or service failures.
  - *Objective*: Add exponential retry policies, S3 Bronze sensors, and Airflow 3 Deadline Alerts for monitoring.

### Milestone M7: Data Quality & Observability
- **#27 [M7] Implement cross-tier data quality validation gates**
  - *Context*: Corrupted data or silent schema drift must be quarantined before reaching analytical marts.
  - *Objective*: Build automated validation gates verifying file size, schema validity, and null checks between tiers.
- **#28 [M7] Add unified pipeline run telemetry reporting**
  - *Context*: Operators need immediate visibility into run performance, record counts, and elapsed latency.
  - *Objective*: Create a reporting utility that aggregates metrics across CloudWatch, Snowflake, and dbt into run manifests with `spotify_snapshot_id`.
- **#29 [M7] Implement automated incident response and replay runbook scripts**
  - *Context*: Operational runbooks must be backed by actionable automation.
  - *Objective*: Build CLI recovery scripts for replaying failed dates, refreshing expired tokens, and purging corrupted partitions.

### Milestone M8: Terraform & CI/CD Hardening
- **#30 [M8] Provision AWS resources (S3, IAM, Lambda, Glue) with Terraform**
  - *Context*: Cloud infrastructure must be 100% reproducible via IaC.
  - *Objective*: Implement Terraform modules for S3 buckets, least-privilege IAM roles, Lambda extractor, and Glue 5.1 job.
- **#31 [M8] Add Terraform linting and security scanning to CI**
  - *Context*: Prevent IaC syntax errors and security regressions.
  - *Objective*: Add `tflint` and static security scanning steps to GitHub Actions workflow.
- **#32 [M8] Configure AWS Budgets and cost threshold alerts**
  - *Context*: Strictly govern the $20/month portfolio budget target.
  - *Objective*: Add Terraform definition for AWS Budget with alerts at $10.00 and $18.00 spend.

### Milestone M9: Power BI & Portfolio Release
- **#33 [M9] Build Power BI semantic model on Snowflake Marts**
  - *Context*: Analytical consumption requires a clean semantic model.
  - *Objective*: Create Power BI model connecting to Snowflake `MARTS` with verified relationships.
- **#34 [M9] Create interactive portfolio dashboard and visual assets**
  - *Context*: Demonstrating business value through executive-ready visuals.
  - *Objective*: Build dashboard pages for playlist trends, track churn/retention, and artist presence; export `.pbit` template.
- **#35 [M9] Final portfolio documentation, demo recording guide, and v1.0.0 release**
  - *Context*: Packaging the platform for senior engineering recruitment.
  - *Objective*: Finalize architecture diagrams, write interview talking points (covering 2026 API, Glue 5.1, Airflow 3, backfills), and tag v1.0.0.
