# Project Backlog & Implementation Roadmap

This backlog establishes the structured, phased implementation roadmap for the **Spotify Analytics Data Platform**. Each milestone maps to an engineering sprint containing atomic, reviewable implementation issues.

---

## Milestone Summary

| Milestone | Title | Status | Target Scope |
| :--- | :--- | :--- | :--- |
| **M0** | **Project Foundation & Architecture Blueprint** | **COMPLETED** | Repository bootstrapping, architecture blueprint, ADRs, cost governance, CI |
| **M1** | **Local Spotify Ingestion** | Planned | Spotify API client, pagination, mock fixtures, parser unit tests |
| **M2** | **AWS Lambda & Bronze Data Lake** | Planned | Serverless extractor, S3 Bronze raw storage, Secrets Manager, CloudWatch |
| **M3** | **Glue / PySpark & Silver Layer** | Planned | PySpark transformation, StructType schemas, array explosion, Parquet Silver |
| **M4** | **Snowflake & Snowpipe** | Planned | Storage integration, external stage, Snowpipe auto-ingest, Landing tables |
| **M5** | **dbt Analytics Engineering** | Planned | Staging models, Kimball dimensional star schema, historical facts, marts |
| **M6** | **Airflow Orchestration** | Planned | Docker Airflow, DAG coordination, external service operators, error handling |
| **M7** | **Data Quality & Observability** | Planned | Cross-tier quality gates, structured telemetry reporting, incident recovery |
| **M8** | **Terraform & CI/CD Hardening** | Planned | Terraform modules (S3, IAM, Lambda, Glue), CI security, AWS Budgets |
| **M9** | **Power BI & Portfolio Release** | Planned | Semantic model, DAX measures, portfolio dashboard, interview showcase |

---

## Detailed Milestone Issues

### Milestone M1: Local Spotify Ingestion
- **#1 [M1] Implement Spotify API OAuth client and authentication abstraction**
  - *Context*: Secure access to Spotify Web API requires OAuth 2.0 Client Credentials token exchange.
  - *Objective*: Build a robust, typed Python client for acquiring, caching, and refreshing bearer tokens.
- **#2 [M1] Implement paginated playlist tracks extractor**
  - *Context*: Monitored playlists exceed Spotify's single-request limit (100 items).
  - *Objective*: Build a pagination engine that retrieves all tracks, handles HTTP 429 rate limits, and yields consolidated snapshots.
- **#3 [M1] Add Spotify response fixtures and unit parser tests**
  - *Context*: Offline unit testing must validate API parsing without live network dependencies.
  - *Objective*: Create synthetic API fixtures and pytest suites covering tracks, artists, albums, and edge-case nulls.
- **#4 [M1] Define ingestion run metadata model and local persistence**
  - *Context*: Ingestion runs must attach standard telemetry (`pipeline_run_id`, timestamps, record counts).
  - *Objective*: Implement Pydantic domain models validating run telemetry and landing raw JSON locally.

### Milestone M2: AWS Lambda & Bronze Data Lake
- **#5 [M2] Define S3 Bronze object layout and naming convention**
  - *Context*: Raw data lake storage must be partitioned deterministically for auditability.
  - *Objective*: Formalize and implement S3 client utilities writing to `bronze/spotify/playlist_tracks/ingestion_date=YYYY-MM-DD/run_id=<id>/`.
- **#6 [M2] Implement AWS Lambda Spotify raw extractor handler**
  - *Context*: Serverless execution decouples extraction from local machines.
  - *Objective*: Package the extractor into a lightweight AWS Lambda handler with short-lived execution (< 60s).
- **#7 [M2] Integrate AWS Secrets Manager for API credentials in Lambda**
  - *Context*: Prevent hardcoded API secrets in Lambda environment variables.
  - *Objective*: Update Lambda handler to fetch credentials dynamically from AWS Secrets Manager using boto3.
- **#8 [M2] Add CloudWatch structured JSON logging to Lambda**
  - *Context*: Ingestion observability requires structured telemetry in log streams.
  - *Objective*: Configure Python logging to emit JSON events containing `pipeline_run_id`, latency, and record counts.

### Milestone M3: Glue / PySpark & Silver Layer
- **#9 [M3] Define explicit PySpark StructType schemas for Bronze & Silver**
  - *Context*: Schema inference causes performance hits and fails silently on drift.
  - *Objective*: Define strict PySpark `StructType` schemas for Bronze JSON and Silver Parquet datasets.
- **#10 [M3] Implement artists and albums normalization logic in PySpark**
  - *Context*: Artist and album metadata is deeply nested within track items.
  - *Objective*: Build PySpark transformation logic extracting deduplicated artist and album entities.
- **#11 [M3] Implement tracks and track-artist bridge extraction**
  - *Context*: Tracks have many-to-many relationships with contributing artists.
  - *Objective*: Explode artist arrays to produce normalized `tracks` and `track_artists` bridge datasets.
- **#12 [M3] Implement historical playlist snapshot normalization & deduplication**
  - *Context*: Longitudinal analysis requires capturing track positions and addition timestamps per snapshot.
  - *Objective*: Transform raw playlist items into a point-in-time snapshot entity dataset.
- **#13 [M3] Write partitioned Parquet serialization and local PySpark tests**
  - *Context*: Silver data must be serialized efficiently and tested locally without AWS.
  - *Objective*: Implement Snappy-compressed Parquet output writing partitioned by date, with local pytest test suite.

### Milestone M4: Snowflake & Snowpipe
- **#14 [M4] Define Snowflake databases, schemas, and RBAC roles**
  - *Context*: Warehouse architecture requires structured schemas and least-privilege security roles.
  - *Objective*: Write DDL scripts creating `LANDING`, `STAGING`, `CORE`, `MARTS` and dedicated roles (`LOADER`, `TRANSFORMER`, `ANALYST`).
- **#15 [M4] Configure AWS IAM storage integration and S3 external stage**
  - *Context*: Secure cross-account access between AWS S3 and Snowflake without static credentials.
  - *Objective*: Create Snowflake Storage Integration pointing to S3 Silver stage with IAM trust relationship.
- **#16 [M4] Implement Snowpipe auto-ingest for Silver Parquet**
  - *Context*: Automated loading into Landing tables upon file arrival in S3.
  - *Objective*: Create Snowpipe definitions with `AUTO_INGEST = TRUE` mapped to SQS event notifications.
- **#17 [M4] Create Snowflake Landing tables and load validation queries**
  - *Context*: Landing tables require exact 1:1 typing with Parquet schemas and audit verification.
  - *Objective*: Write DDL for `landing_artists`, `landing_albums`, `landing_tracks`, `landing_playlist_snapshots` and validation queries.

### Milestone M5: dbt Analytics Engineering
- **#18 [M5] Initialize dbt Core project with Snowflake adapter**
  - *Context*: Centralizing analytical transformations requires a version-controlled dbt project.
  - *Objective*: Scaffold dbt project (`dbt_project.yml`, profiles template, directory structure, packages).
- **#19 [M5] Build dbt staging models for Landing sources**
  - *Context*: Raw Landing tables require light cleansing, naming conventions, and typing.
  - *Objective*: Create staging views `stg_spotify_artists`, `stg_spotify_albums`, `stg_spotify_tracks`, `stg_spotify_playlist_snapshots`.
- **#20 [M5] Build Kimball core dimensions and track-artist bridge**
  - *Context*: Star schema reporting requires clean dimensions and bridge relationships.
  - *Objective*: Implement `dim_track`, `dim_artist`, `dim_album`, `dim_playlist`, and `bridge_track_artist` using surrogate hashing.
- **#21 [M5] Build incremental fact_playlist_snapshot model**
  - *Context*: Longitudinal snapshots must be loaded incrementally without reprocessing all history.
  - *Objective*: Build incremental dbt model `fact_playlist_snapshot` keyed by composite snapshot grain.
- **#22 [M5] Build analytical marts and dbt data quality tests**
  - *Context*: Business metrics (churn, retention, popularity trajectory) serve BI dashboards.
  - *Objective*: Implement `mart_artist_performance`, `mart_playlist_trends`, `mart_playlist_changes` and comprehensive dbt tests.

### Milestone M6: Airflow Orchestration
- **#23 [M6] Create local Docker Compose Airflow environment**
  - *Context*: Cost-effective orchestration testing requires containerized local Airflow.
  - *Objective*: Create `docker-compose.yml`, custom Dockerfile with AWS/Snowflake providers, and setup documentation.
- **#24 [M6] Implement end-to-end daily orchestration DAG**
  - *Context*: Coordinating Lambda, Glue, Snowpipe, and dbt in a scheduled workflow.
  - *Objective*: Build `spotify_daily_snapshot_dag` defining task sequence and parameter passing.
- **#25 [M6] Add external execution operators (Lambda, Glue, Snowflake, dbt)**
  - *Context*: Enforcing Airflow as orchestrator requires external operator integration.
  - *Objective*: Configure `LambdaInvokeFunctionOperator`, `GlueJobOperator`, and dbt execution tasks.
- **#26 [M6] Implement pipeline retries, SLA sensors, and failure alerts**
  - *Context*: Production pipelines must handle transient network or service failures.
  - *Objective*: Add exponential retry policies, S3 Bronze sensors, Snowflake landing validation sensors, and failure callbacks.

### Milestone M7: Data Quality & Observability
- **#27 [M7] Implement cross-tier data quality validation gates**
  - *Context*: Bad data must be blocked before reaching analytical marts.
  - *Objective*: Build automated validation gates verifying row counts, schema validity, and null checks between tiers.
- **#28 [M7] Add unified pipeline run telemetry reporting**
  - *Context*: Operators need end-to-end visibility into duration and record counts per run.
  - *Objective*: Create a reporting utility that aggregates metrics across CloudWatch, Snowflake, and dbt into run manifests.
- **#29 [M7] Implement automated incident response and replay runbook scripts**
  - *Context*: Operational runbooks must be backed by actionable automation.
  - *Objective*: Build CLI recovery scripts for replaying failed dates and purging corrupted partitions.

### Milestone M8: Terraform & CI/CD Hardening
- **#30 [M8] Provision AWS resources (S3, IAM, Lambda, Glue) with Terraform**
  - *Context*: Cloud infrastructure must be 100% reproducible via IaC.
  - *Objective*: Implement Terraform modules for S3 buckets, least-privilege IAM roles, Lambda extractor, and Glue jobs.
- **#31 [M8] Add Terraform linting and security scanning to CI**
  - *Context*: Prevent IaC syntax errors and security regressions.
  - *Objective*: Add `tflint` and `checkov` static analysis steps to GitHub Actions workflow.
- **#32 [M8] Configure AWS Budgets and cost threshold alerts**
  - *Context*: Strictly enforce the $20/month portfolio budget limit.
  - *Objective*: Add Terraform definition for AWS Budget with alerts at $10.00 and $18.00 spend.

### Milestone M9: Power BI & Portfolio Release
- **#33 [M9] Build Power BI semantic model on Snowflake Marts**
  - *Context*: Analytical consumption requires a clean semantic model.
  - *Objective*: Create Power BI model connecting to Snowflake `MARTS` with verified relationships.
- **#34 [M9] Create interactive portfolio dashboard and visual assets**
  - *Context*: Demonstrating business value through executive-ready visuals.
  - *Objective*: Build dashboard pages for playlist trends, track churn/retention, and artist performance; capture screenshots.
- **#35 [M9] Final portfolio documentation, demo recording guide, and v1.0.0 release**
  - *Context*: Packaging the platform for senior engineering recruitment.
  - *Objective*: Finalize architecture diagrams, write LinkedIn showcase article, create interview talking points, and tag v1.0.0.
