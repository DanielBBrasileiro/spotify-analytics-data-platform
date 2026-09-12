# Spotify Analytics Data Platform — Master Architecture Blueprint

**Version:** 0.1.1
**Status:** M1 Complete / Local Ingestion Contract Implemented
**Author:** Daniel Barbosa
**Target Environment:** AWS (us-east-1), Snowflake, Docker, Python 3.12, AWS Glue 5.1, Apache Airflow 3.x

---

## 1. Executive Summary

The **Spotify Analytics Data Platform** is an enterprise-grade data platform engineered to extract, process, model, and analyze longitudinal Spotify playlist snapshots. Unlike introductory data engineering tutorials that overwrite state daily or collapse ETL logic into monolithic scripts, this platform enforces production standards: strict decoupling between orchestration and execution, immutable data lake storage, distributed Spark transformations for unnesting semi-structured JSON, continuous automated Snowflake ingestion via Snowpipe, Kimball dimensional modeling with dbt Core, automated data testing, and target-governed infrastructure as code.

Version 0.1.1 formally aligns the platform with the 2026 Spotify Web API specifications, AWS Glue 5.1 runtimes, Apache Airflow 3.x architecture, and mathematically sound canonical fact grain modeling.

---

## 2. Project Objectives

1. **Demonstrate Senior/Staff Engineering Practices**: Implement production-grade architecture, infrastructure as code, CI/CD, modular code, and rigorous documentation suitable for international senior data engineer evaluations.
2. **Longitudinal Analytical Capability**: Ingest and model historical playlist snapshots to measure track longevity, playlist churn, artist concentration, position movement, and composition shifts over time across monitored user-owned or collaborative playlists.
3. **Strict Separation of Concerns**: Maintain Apache Airflow 3.x strictly as an orchestrator, AWS Glue 5.1/PySpark as the data lake processing engine, Snowflake as the analytical warehouse, and dbt Core as the business modeling tool.
4. **Budget & Cost Governance**: Design the entire infrastructure around a portfolio budget target ceiling of **$20.00 USD/month**, leveraging serverless architectures, ephemeral execution, and aggressive warehouse auto-suspension.
5. **Secure Credential Architecture**: Zero secrets committed, OAuth 2.0 Authorization Code flow with refresh token persistence in AWS Secrets Manager, least-privilege IAM policies, and encrypted storage.

---

## 3. Non-Goals

- **Real-Time Streaming**: This platform does not ingest Kafka/Kinesis streams. Spotify's API does not emit real-time event streams; a batch snapshot cadence (daily/hourly) is the technically appropriate pattern.
- **Arbitrary Global Editorial Scraping**: The platform does not claim or attempt unsupported scraping of arbitrary public Spotify editorial playlists without authorized access. Monitored playlists are user-owned, followed, or collaborative playlists accessible under authorized application scopes.
- **Over-Engineered Infrastructure**: Kubernetes (EKS), Apache Flink, or Databricks are explicitly excluded to prevent unnecessary cost and administrative complexity.
- **Airflow Compute Monolith**: Airflow will not execute data extraction or data transformation in worker memory.
- **Production Commercial SLA**: This is a portfolio demonstration platform; 99.999% high-availability guarantees and multi-region failover are out of scope.

---

## 4. Business Use Cases

1. **Track Churn & Retention Analysis**: Determine the exact entry date, exit date, and retention tenure (days present) of tracks within monitored playlists.
2. **Artist Concentration & Representation**: Analyze which artists occupy the greatest share of playlist real estate and how artist representation shifts over months.
3. **Playlist Volatility Tracking**: Quantify turnover rates (daily additions vs. removals) across monitored playlists to evaluate curation dynamics.
4. **Positional Trajectory**: Track daily chart and rank movement, measuring best position achieved and average position over a song's lifecycle.
5. **Composition Evolution**: Observe longitudinal changes in explicit content share, track duration distribution, and release recency (catalog age).

---

## 5. Engineering Use Cases

1. **Idempotent Data Lake Ingestion**: Safely re-run ingestion pipelines for any historical date without creating duplicate records or corrupting warehouse state.
2. **Schema Drift Quarantine**: Prevent upstream Spotify JSON changes from breaking downstream warehouse queries through explicit PySpark schema enforcement and item-type validation.
3. **Automated Snowpipe Loading**: Ingest partitioned Parquet files into Snowflake within seconds of creation via Amazon S3 event notifications.
4. **Deterministic Merge Backfills**: Enable arbitrary historical backfills and retries using dbt SQL `MERGE` on a canonical composite unique key.
5. **Source Version Tracking**: Track upstream playlist mutations via Spotify's native `snapshot_id`.

---

## 6. Architecture

```mermaid
flowchart TD
    subgraph Auth["OAuth 2.0 Authentication"]
        Operator["Operator Setup<br/>(One-Time Interactive)"] -->|Auth Code Consent| SpotifyAuth["Spotify Accounts Service"]
        SpotifyAuth -->|Refresh Token| SecMgr[("AWS Secrets Manager<br/>(spotify/api/credentials)")]
    end

    subgraph Source["Source Layer"]
        API["Spotify Web API<br/>(/v1/playlists/{id}/items)"]
    end

    subgraph Orchestration["Orchestration Layer (Local / Docker)"]
        Airflow["Apache Airflow 3.x<br/>• Task SDK Coordination<br/>• External Service Operators<br/>• Deadline Alerts & Quality Gates"]
    end

    subgraph Lake["AWS Data Lake (us-east-1)"]
        Lambda["AWS Lambda Extractor<br/>(Python 3.12, Secrets Manager)"]
        S3Bronze[("Amazon S3 Bronze<br/>• Immutable Raw JSON<br/>• partitioned by date/run_id")]
        Glue["AWS Glue 5.1 / PySpark 3.5.6<br/>• Schema Enforcement<br/>• Explode Arrays<br/>• Deduplication"]
        S3Silver[("Amazon S3 Silver<br/>• Curated Parquet<br/>• Snappy Compressed")]
    end

    subgraph Warehouse["Snowflake Analytical Warehouse"]
        SQS["AWS SQS / S3 Event Notification"]
        Snowpipe["Snowpipe Continuous Ingestion"]
        Landing["LANDING Schema<br/>(1:1 Silver Parquet Mapping + Metadata)"]
        dbt["dbt Core Engine<br/>• Staging Views<br/>• Dimensional Core<br/>• Analytical Marts"]
        Core["CORE & MARTS Schemas<br/>• Star Schema Tables<br/>• Longitudinal Marts"]
    end

    subgraph Consumption["Serving & BI"]
        PowerBI["Power BI Dashboard<br/>(DirectQuery / Scheduled Import)"]
    end

    %% Flow connections
    SecMgr -.->|Fetch Token| Lambda
    Lambda -->|Refresh Token Exchange & GET| API
    API -->|HTTPS JSON (50 items/page)| Lambda
    Lambda -->|PutObject| S3Bronze
    S3Bronze -->|Read Raw JSON| Glue
    Glue -->|Write Parquet| S3Silver
    S3Silver -->|S3 Event| SQS
    SQS -->|Trigger Load| Snowpipe
    Snowpipe -->|Copy Into| Landing
    Landing -->|Transform| dbt
    dbt -->|Incremental Merge| Core
    Core -->|Query| PowerBI

    %% Orchestration triggers
    Airflow -.->|1. Trigger| Lambda
    Airflow -.->|2. Trigger| Glue
    Airflow -.->|3. Validate Load| Landing
    Airflow -.->|4. Execute| dbt
```

---

## 7. Component Responsibilities

| Component | Responsibility | Bound Engine |
| :--- | :--- | :--- |
| **Spotify API** | Source of truth for playlist snapshots, items, tracks, artists, and albums. | External HTTPS REST |
| **AWS Secrets Manager** | Secure vault storing `client_id`, `client_secret`, and long-lived `refresh_token`. | AWS Secrets Manager |
| **AWS Lambda** | Serverless extractor. Exchanges refresh token for short-lived access token, paginates `/items`, and lands raw JSON in S3 Bronze. | AWS Lambda (Python 3.12) |
| **Amazon S3** | Durable, multi-tiered object storage (Bronze = Raw JSON, Silver = Parquet, Metadata = Manifests). | AWS S3 Standard |
| **AWS Glue 5.1** | Parses semi-structured JSON, enforces schemas, validates item types, explodes arrays, deduplicates, writes partitioned Parquet. | Apache Spark 3.5.6 / Python 3.11 |
| **Snowpipe** | Event-driven, serverless continuous ingestion of Silver Parquet files into Snowflake Landing tables. | Snowflake Snowpipe |
| **Snowflake** | High-performance columnar data warehouse executing SQL queries with micro-partitioning. | Snowflake Virtual Warehouse (`X-Small`) |
| **dbt Core** | Orchestrates warehouse transformations: staging, dimensions, incremental facts, bridge tables, marts, tests. | dbt Core CLI |
| **Apache Airflow 3.x** | Orchestrates end-to-end workflow: triggers Lambda/Glue, coordinates sensors, validates ingestion, runs dbt. | Docker Compose / Task SDK |
| **Power BI** | Business reporting, longitudinal trend visualization, churn metrics, and interactive dashboards. | Power BI Desktop / Service |
| **Terraform** | Declarative infrastructure as code for AWS resources, IAM roles, and storage integrations. | Terraform CLI |

---

## 8. Data Flow

1. **Extraction (T0)**: Airflow triggers the Lambda extractor with target playlist IDs, `snapshot_date`, and generated physical `pipeline_run_id`.
2. **Token Refresh & Bronze Landing (target state)**: Lambda obtains credentials from the configured credential provider, refreshes a short-lived access token, paginates `GET /v1/playlists/{id}/items` (limit=50), captures `spotify_snapshot_id`, and writes raw JSON to `s3://<bucket>/bronze/spotify/playlist_tracks/ingestion_date=YYYY-MM-DD/run_id=<run_id>/playlist_<id>.json`. Issue #7 supplies Secrets Manager credentials for non-local execution and explicit environment credentials only for local mode. The `< 30s` runtime objective is not yet a measured guarantee.
3. **Silver Transformation (T0 + 60s)**: Airflow triggers the AWS Glue 5.1 PySpark job. The job reads one Bronze playlist object per invocation, enforces explicit StructType schemas, validates item types (extracting tracks and quarantining non-tracks), explodes artist relationships, deduplicates entities, and writes Snappy Parquet to S3 Silver under `ingestion_date/run_id/playlist_id` publication prefixes so independent playlists/runs cannot overwrite each other.
4. **Warehouse Landing (T0 + 120s)**: S3 object creation triggers an SQS event consumed by Snowpipe, loading Parquet partitions into Snowflake `LANDING` tables along with file audit metadata (`METADATA$FILENAME`, `METADATA$FILE_ROW_NUMBER`).
5. **Dimensional Modeling (T0 + 180s)**: Airflow validates row counts in Landing and triggers `dbt build`. dbt updates staging views, incrementally merges core dimensions, merges `fact_playlist_snapshot` on `snapshot_pk`, and refreshes analytical marts.
6. **Reporting (T0 + 300s)**: Power BI queries curated models in Snowflake `MARTS`.

---

## 9. S3 Data Lake Strategy

M2 centralizes Bronze object naming in `spotify_data_platform.storage` so local
and future cloud writers share one key contract. `build_bronze_playlist_key(...)`
returns the Hive-style object key and `build_bronze_playlist_uri(...)` adds a
validated general-purpose bucket name. The helper accepts only a `date`, UUID v4,
and 22-character playlist ID; callers cannot inject arbitrary prefixes or relative
path segments. It performs no S3 API calls and does not provision buckets.

For ingestion runs, `ingestion_date` is the UTC physical capture date. It remains
distinct from the canonical business `snapshot_date`, which can intentionally
differ during retries and historical backfills.

Issue #6 adds the Lambda runtime adapter on top of this contract. The handler
validates `playlist_ids`, UUID v4 `pipeline_run_id`, and `snapshot_date`, reuses the
M1 OAuth/extraction code, creates one `PipelineRunMetadata` record per successful
playlist observation, and publishes the source-preserving JSON with conditional
`PutObject(IfNoneMatch="*")`. S3 writes request SSE-S3 encryption and never silently
replace an existing canonical object. Local and S3 writers share the same Bronze
validation/serialization function.

The deployment entrypoint is `lambda/src/extractor.py`; the tested implementation
resides in `spotify_data_platform.lambda_runtime`. No bucket, IAM role, Lambda
function, or secret is provisioned by Issues #5/#6/#7. Issue #7 adds an environment-
aware credential provider: explicit local mode reads process environment, while
cloud mode calls Secrets Manager `GetSecretValue` for the configured secret id.
Credentials and the auth client are cached for a warm container; `invalid_grant`
invalidates both caches so an operator-updated secret can be read on a later
invocation. Secret values are never included in provider error messages. Durable
write-back of a rotated refresh token is not part of Issue #7 because it would add
Secrets Manager write permissions. Structured lifecycle logging remains Issue #8.

```
s3://<platform-bucket>/
├── bronze/
│   └── spotify/
│       └── playlist_tracks/
│           └── ingestion_date=YYYY-MM-DD/
│               └── run_id=<pipeline_run_id>/
│                   └── playlist_<id>.json
├── silver/
│   ├── artists/
│   │   └── ingestion_date=YYYY-MM-DD/
│   │       └── run_id=<pipeline_run_id>/playlist_id=<playlist_id>/part-*.parquet
│   ├── albums/
│   │   └── ingestion_date=YYYY-MM-DD/
│   │       └── run_id=<pipeline_run_id>/playlist_id=<playlist_id>/part-*.parquet
│   ├── tracks/
│   │   └── ingestion_date=YYYY-MM-DD/
│   │       └── run_id=<pipeline_run_id>/playlist_id=<playlist_id>/part-*.parquet
│   ├── track_artists/
│   │   └── ingestion_date=YYYY-MM-DD/
│   │       └── run_id=<pipeline_run_id>/playlist_id=<playlist_id>/part-*.parquet
│   ├── playlist_snapshots/
│   │   └── ingestion_date=YYYY-MM-DD/
│   │       └── run_id=<pipeline_run_id>/playlist_id=<playlist_id>/part-*.parquet
│   └── playlist_observations/
│       └── ingestion_date=YYYY-MM-DD/
│           └── run_id=<pipeline_run_id>/playlist_id=<playlist_id>/part-*.parquet
└── metadata/
    └── pipeline_runs/
        └── year=YYYY/month=MM/
            └── run_<pipeline_run_id>.json
```

---

## 10. File Formats

- **Bronze Layer**: UTF-8 JSON. Preserves 100% of raw API payloads, nested structures, and response headers for complete auditability.
- **Silver Layer**: Apache Parquet with Snappy compression. Columnar, strictly typed, splittable, and optimized for Snowflake ingestion.
- **Metadata Layer**: JSON execution manifests documenting run telemetry and audit metrics.

---

## 11. Partitioning Strategy

- **Bronze**: Partitioned by `ingestion_date=YYYY-MM-DD/run_id=<pipeline_run_id>/`. Isolates individual execution payloads and prevents collision during retries.
- **Silver**: Partitioned by `ingestion_date=YYYY-MM-DD/run_id=<pipeline_run_id>/playlist_id=<playlist_id>/`. The date remains the leading pruning key while run/playlist scopes prevent same-day publication collisions.

---

## 12. Spotify Extraction Strategy

- **Endpoint**: `/v1/playlists/{playlist_id}/items`.
- **Authentication**: OAuth 2.0 Authorization Code Flow with Refresh Token. Initial user consent provides the `refresh_token`; scheduled executions dynamically request short-lived bearer tokens via `POST https://accounts.spotify.com/api/token` (`grant_type=refresh_token`).
- **Scopes**: `playlist-read-private`, `playlist-read-collaborative`.
- **Source Lineage**: Captures `spotify_snapshot_id` returned on the playlist response.

---

## 13. API Pagination Strategy

- Under Spotify Web API specifications for `/v1/playlists/{id}/items`, the maximum `limit` is **50 items per request**.
- The client initializes with `limit=50`, `offset=0`, advances by the actual item count, and validates that `total` and `next` agree before returning a complete result.
- The items response does not contain `snapshot_id`. The client reads playlist metadata before pagination and checks `GET /v1/playlists/{id}?fields=snapshot_id` after every page. An observed version change aborts the entire extraction; this is optimistic validation, not a pinned server-side transaction.
- See [Local Ingestion](LOCAL_INGESTION.md) for the implemented raw payload contract, request limits, and retry behavior.

---

## 14. Rate-Limit & Error Strategy

- Spotify emits HTTP `429 Too Many Requests` when throttled, including a `Retry-After` header.
- The Python client implements exponential backoff with jitter respecting the `Retry-After` value.
- Maximum retry limit: 5 retries after the initial attempt per API request. Exhausted HTTP 429 responses raise `RateLimitExceededException`; the future Lambda/Airflow adapters will report and handle that failure.

---

## 15. Pipeline Run ID Strategy

- `pipeline_run_id` is a **UUID v4** generated per Airflow DAG run.
- It is **intentionally non-deterministic** and serves strictly as a physical execution tracking identifier.
- Business observation identity is defined by `snapshot_date` (calendar date) and upstream `spotify_snapshot_id`.
- Retries of the same business date receive new physical `pipeline_run_id` values but merge idempotently into the same canonical warehouse keys.

---

## 16. Raw-Data Immutability

- S3 Bronze is append-only.
- Raw files are never overwritten, edited, or deleted in place during normal pipeline runs.
- Reprocessed runs land in a new `run_id` subdirectory.

---

## 17. Spark Transformation Strategy

- Implemented on **AWS Glue 5.1** running Apache Spark 3.5.6 and Python 3.11.
- Ingests raw Bronze JSON using explicit `StructType` schemas.
- Validates the 2026 playlist-item shape at `entry.item`, extracting direct
  `type = 'track'` items with provider-backed track IDs and quarantining episodes,
  unavailable/null items, unsupported types, and local tracks without provider IDs.
- Explodes nested artist arrays to produce normalized `tracks` and `track_artists` datasets.
- Coalesces output partitions to avoid tiny-file fragmentation.

---

## 18. Schema Enforcement

- Schema inference (`inferSchema=true`) is strictly prohibited in production Spark jobs.
- Schemas are defined in `glue/schemas/` using explicit PySpark types.
- Unsupported or malformed records are routed to `_corrupt_record` handling.
- Note: Per 2026 Spotify API updates, deprecated popularity and label fields are excluded.

---

## 19. Snowflake Ingestion Strategy

- Leverages an external S3 stage backed by an AWS IAM Storage Integration.
- Snowpipe parses Parquet files into Landing tables using explicit column mappings and captures audit columns:
  `_loaded_at`, `_file_name` (`METADATA$FILENAME`), `_file_row_number` (`METADATA$FILE_ROW_NUMBER`).

---

## 20. Snowpipe Design

- Configured with `AUTO_INGEST = TRUE` via Amazon SQS notifications.
- **Idempotency Clarification**: Snowpipe file-load tracking guarantees that a specific S3 object is not loaded multiple times by the pipe. However, **Snowpipe does NOT provide application business deduplication**. Business deduplication is enforced downstream in dbt via canonical keys and SQL `MERGE`.

---

## 21. Snowflake Database & Schema Organization

```
SPOTIFY_ANALYTICS (Database)
├── LANDING
│   ├── landing_artists
│   ├── landing_albums
│   ├── landing_tracks
│   ├── landing_track_artists
│   ├── landing_playlist_snapshots
│   └── landing_playlist_observations
├── STAGING (dbt managed views)
│   ├── stg_spotify_artists
│   ├── stg_spotify_albums
│   ├── stg_spotify_tracks
│   ├── stg_spotify_track_artists
│   ├── stg_spotify_playlist_snapshots
│   └── stg_spotify_playlist_observations
├── CORE (dbt managed dimensional tables)
│   ├── dim_artist
│   ├── dim_album
│   ├── dim_track
│   ├── dim_playlist
│   ├── bridge_track_artist
│   └── fact_playlist_snapshot
└── MARTS (dbt managed analytical tables / views)
    ├── mart_artist_presence
    ├── mart_playlist_trends
    ├── mart_track_lifecycle
    └── mart_playlist_changes
```

---

## 22. dbt Architecture

- **Tool**: dbt Core.
- **Adapter**: `dbt-snowflake`.
- **Materializations**:
  - `staging`: Views.
  - `core` dimensions: Table (incremental merge for dimensions).
  - `core` fact (`fact_playlist_snapshot`): Incremental with `incremental_strategy = 'merge'`.
  - `marts`: Tables.
- **Packages**: `dbt-labs/dbt_utils`.

---

## 23. Dimensional Model

Refer to [`docs/DATA_MODEL.md`](DATA_MODEL.md) for full ERD and schema dictionaries. Core entities include:
- `dim_track`: Track attributes, surrogate key `track_pk`.
- `dim_artist`: Artist attributes, surrogate key `artist_pk`.
- `dim_album`: Album metadata, surrogate key `album_pk`.
- `dim_playlist`: Playlist metadata, surrogate key `playlist_pk`.
- `bridge_track_artist`: Resolves many-to-many track/artist billing, surrogate key `bridge_pk`.
- `fact_playlist_snapshot`: Historical snapshot fact, surrogate key `snapshot_pk`.

---

## 24. Historical Snapshot Model

- **Canonical Grain**: `playlist_id` + `snapshot_date` + `track_position`.
  *(One canonical position slot per playlist per business observation date).*
- The `track_id` is the observed dimensional entity occupying that slot on that date.
- Surrogate Key: `snapshot_pk = hash(playlist_id || '-' || snapshot_date || '-' || track_position)`.
- Lineage Attributes: `spotify_snapshot_id`, `pipeline_run_id`, `snapshot_timestamp`, `added_at`.

---

## 25. Incremental Loading Strategy

- The dbt fact model uses `incremental_strategy = 'merge'` on `unique_key = 'snapshot_pk'`.
- **Normal Run**: Processes the specified `snapshot_date`.
- **Backfill Run**: Accepts explicit start and end date variables:
  `dbt build --select fact_playlist_snapshot --vars '{"start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD"}'`.
- **Retry**: Re-running an existing date updates/matches the canonical slot records rather than duplicating them.

---

## 26. Idempotency

Idempotency is enforced end-to-end:
- Bronze: Scoped by execution `run_id`.
- Silver: Parquet publications overwrite only their unique `ingestion_date/run_id/playlist_id` scope; another playlist or physical run on the same day is never replaced.
- Snowflake Core / Marts: Enforced via `MERGE` on deterministic surrogate keys (`snapshot_pk`).

---

## 27. Deduplication

1. **Spark Tier**: Deduplicates artist and album entities extracted across multiple tracks within the run batch.
2. **Staging Tier**: Uses `ROW_NUMBER() OVER (PARTITION BY ... ORDER BY _loaded_at DESC)` to isolate the most recent landing record per slot.
3. **Core Tier**: dbt `MERGE` guarantees a single row per canonical unique key.

---

## 28. Retry Strategy

- **Lambda**: Exponential backoff on HTTP 429 and 5xx; 5 retry attempts.
- **Airflow 3**: Task retries with exponential backoff; Deadline Alerts for SLA monitoring.
- **Glue**: Configured with `MaxRetries = 1` to prevent runaway compute costs.

---

## 29. Backfill & Reprocessing

To reprocess historical data:
1. Verify raw JSON exists in S3 Bronze for target dates.
2. Re-run Glue 5.1 ETL for target dates to rebuild Silver Parquet.
3. Allow Snowpipe to ingest or execute manual copy.
4. Execute `dbt build` with explicit backfill date ranges.

---

## 30. Schema Evolution

- Upstream Spotify API schema changes:
  - Bronze JSON captures new fields automatically without failure.
  - PySpark explicit `StructType` ignores unmapped attributes, maintaining pipeline stability.
  - New attributes are formally adopted by updating schemas, Parquet output, and dbt models in a controlled release.

---

## 31. Data Quality

Cross-tier validation gates:
- **Bronze Gates**: File size > 0 bytes, valid JSON structure, non-empty payload.
- **Silver Gates**: Required non-null keys (`track_id`, `artist_id`), positive track durations (`duration_ms > 0`).
- **Warehouse Gates (dbt Tests)**:
  - `not_null` and `unique` on all primary and surrogate keys.
  - `relationships` tests enforcing foreign keys between facts, dimensions, and bridge tables.
  - Custom SQL assertions: Valid date bounds, positive durations.

---

## 32. Observability

M2 implements structured JSON telemetry for the Lambda ingestion boundary. Every
event carries `pipeline_run_id`, `playlist_id`, `snapshot_date`, event `timestamp`,
`duration_ms`, status, component/version fields, and a `spotify_snapshot_id` key.
The source version is `null` for events emitted before playlist metadata establishes it.

Implemented Lambda events are `EXTRACTION_START`, `PAGINATION_PAGE_FETCHED`,
`S3_WRITE_SUCCESS`, `EXTRACTION_COMPLETE`, and sanitized `EXTRACTION_FAILED`.
Page events are emitted only after the page passes source-version validation; failure
events expose only the exception type, not exception text, credentials, or payloads.

CloudWatch capture is a deployment target, not a provisioned resource. Log groups,
retention, alarms, metric filters, Glue telemetry, Airflow task logs, Snowflake
`COPY_HISTORY`, dbt artifacts, and cross-tier metrics remain later milestone work.

---

## 33. Security

- Zero hardcoded secrets in version control.
- OAuth 2.0 Authorization Code Flow with Refresh Token stored in AWS Secrets Manager.
- Short-lived operational access tokens (1 hour).
- Encryption at rest (SSE-S3 / KMS, Snowflake TDE) and in transit (TLS 1.3).

---

## 34. IAM Philosophy

- Principle of Least Privilege:
  - Lambda Role: `secretsmanager:GetSecretValue` on `spotify/api/credentials`, `s3:PutObject` on `bronze/*`.
  - Glue Role: `s3:GetObject` on `bronze/*`, `s3:PutObject` on `silver/*`, CloudWatch logs.
  - Snowflake Integration: Read-only cross-account role on `silver/*`.

---

## 35. Secrets Management

- Local: `.env` (gitignored), template in `.env.example` using `AWS_PROFILE=spotify-dev`.
- AWS: AWS Secrets Manager.
- Snowflake: Dedicated service roles (`SPOTIFY_TRANSFORMER`, `SPOTIFY_LOADER`), never `SYSADMIN`.

---

## 36. Terraform Strategy

- All cloud resources defined in `infra/terraform/`.
- Modular layout (`modules/s3`, `modules/iam`, `modules/lambda`, `modules/glue`, `modules/monitoring`).
- Plan and validate in CI; zero live infrastructure deployed without explicit user confirmation.

---

## 37. CI/CD Strategy

- GitHub Actions executes static checks on pull requests and pushes to `main`.
- Tools: Ruff (`ruff check .`, `ruff format --check .`), pytest (`pytest`).
- Zero cloud credentials required; runs completely offline.

---

## 38. Testing Strategy

- Unit Tests: Offline tests using synthetic Spotify 2026 JSON fixtures.
- PySpark Tests: Local SparkSession validating unnesting and schema enforcement.
- Warehouse Tests: dbt schema assertions and singular SQL tests.

---

## 39. Local Development

- Local Python 3.12 virtualenv managed via `uv` or `pip`.
- Airflow 3.x containerized via Docker Compose.
- Validated run-lineage metadata and immutable local Bronze JSON persistence mirror
  the future S3 object hierarchy under the gitignored `data/` directory.
- Fast inner-loop feedback via `make check`.

---

## 40. Cloud Development

- Deployed on-demand via Terraform into `us-east-1`.
- Clean teardown via `terraform destroy` post-demonstration.

---

## 41. Cost Controls

- Portfolio budget target: **≤ $20.00 USD / month** (operational alert threshold).
- AWS Lambda Free Tier (400,000 GB-seconds and 1M requests/month).
- Snowflake `X-Small` warehouse with `AUTO_SUSPEND = 60`.
- CloudWatch log retention capped at 7 days.
- Zero always-on compute (no MWAA, no NAT Gateways, no EMR).

---

## 42. Failure Scenarios

1. **Token Invalidation / Expiration**: A rejected refresh token (`invalid_grant`) clears the process-local credential/auth cache and raises `InvalidGrantException`. Structured operator notification is Issue #8/later orchestration work; the runtime does not claim an alert today.
2. **API Rate Limiting (429)**: Backoff with jitter respecting `Retry-After`.
3. **Mid-Pagination Playlist Mutation**: `spotify_snapshot_id` changes during pagination; extraction aborts and restarts to preserve atomic snapshot integrity.
4. **dbt Test Assertion Failure**: Pipeline halts, preventing bad data from materializing in `MARTS`.

---

## 43. Recovery Scenarios

1. **Token Re-Authorization**: Operator repeats the external authorization flow and updates Secrets Manager with the new refresh token. No setup utility or Secrets Manager write path is implemented in M2.
2. **Historical Backfill**: Re-run Glue ETL over Bronze history, followed by dbt merge backfill.
3. **Partition Purge**: Delete target Silver partition and re-trigger pipeline for that date.

---

## 44. Definition of Done

A pipeline feature is complete when:
1. Code adheres to PEP 8 / Ruff.
2. Unit tests achieve > 90% coverage on new logic.
3. Documentation and ADRs reflect current implementation.
4. `make check` passes with exit code 0.
5. Zero secrets committed; zero unbudgeted cloud resources left running.

---

## 45. Portfolio & Demo Strategy

- Public GitHub repository with clean Git history and architectural rigor.
- Realistic mock fixtures and reproducible demonstration workflows.
- Professional engineering communication avoiding tutorial tropes.

---

## 46. Interview Talking Points

- **Why Authorization Code + Refresh Token instead of Client Credentials?** Client Credentials lacks user scope context and cannot access private/collaborative playlists under modern Spotify Development Mode constraints.
- **Why snapshot_id vs. pipeline_run_id?** `pipeline_run_id` tracks physical pipeline execution lineage; `spotify_snapshot_id` tracks upstream state versioning.
- **Why is the canonical fact grain playlist_id + snapshot_date + track_position?** Decouples observation identity from physical run timestamps, ensuring deterministic merge idempotency across retries and backfills.
- **Why Spark and dbt?** Spark handles semi-structured array explosion and Parquet serialization on low-cost Glue DPUs; dbt handles modular SQL dimensional modeling and warehouse analytics.
- **How is cost controlled?** Ephemeral serverless execution, 60-second Snowflake auto-suspension, and zero always-on infrastructure.

---

## 47. Future Improvements

- Evaluate **Apache Iceberg** tables on S3 Silver for open-table-format time travel.
- Implement **Soda Core** or **Great Expectations** for advanced cross-tier data contracts.
- Automated OIDC-based GitHub Actions deployment.
