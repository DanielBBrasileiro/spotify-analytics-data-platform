# Spotify Analytics Data Platform

[![CI](https://github.com/DanielBBrasileiro/spotify-analytics-data-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/DanielBBrasileiro/spotify-analytics-data-platform/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Release: v1.0.0](https://img.shields.io/badge/Release-v1.0.0-brightgreen.svg)](https://github.com/DanielBBrasileiro/spotify-analytics-data-platform/releases/tag/v1.0.0)

> Production-oriented data engineering portfolio with offline contracts plus a bounded live
> cloud validation of S3 -> Glue 5.1 -> Snowflake/Snowpipe -> dbt Core. The target source-side
> path still includes AWS Lambda for live Spotify extraction. Local Airflow orchestration and
> BI serving views are implemented and have now been exercised against the bounded live cloud
> slice. Terraform IaC, Airflow 3 Deadline Alerts, cross-tier quality/telemetry and recovery tooling are versioned in the repository. Power BI is intentionally deferred from v1.0.0.

---

### Project Status: Bounded Cloud Slice — Airflow Orchestration and Serving Live-Validated
> **Validated end to end for the bounded portfolio slice:** three CC0-derived Bronze snapshots
> were uploaded to S3, processed by AWS Glue 5.1 into 18 Silver Parquet objects across six
> datasets, exposed through a least-privilege Snowflake Storage Integration and external stage,
> auto-ingested by six Snowpipes, and modeled with dbt Core in Snowflake. The Airflow-orchestrated
> live `dbt build` completed with **152/152 passing nodes/tests**, including four consumption-ready
> `BI_*` views. A one-day replay of 2026-09-11 preserved **12 rows / 12 unique fact grains** for
> that date and **36 total fact rows**, proving the incremental merge path is idempotent for the
> validated slice. A live Spotify Web API Lambda extraction is not claimed;
> the reproducible portfolio demo intentionally starts from the CC0 adapter described below.

> **Portfolio data boundary:** the current reproducible cloud demo uses a CC0 public playlist
> corpus for source track/artist/playlist metadata and generates the three-day membership,
> positions, snapshot IDs, and missing compatibility fields deterministically. Those temporal
> analytics are synthetic and must not be presented as observed Spotify behavior. Live Web API
> analytics remain a separately governed path. See
> [ADR-0009](docs/adr/0009-cc0-source-with-synthetic-temporal-demo.md).

---

## 1. Architecture Overview

The platform implements a decoupled lakehouse-to-warehouse architecture where compute workloads are delegated to specialized engines while Apache Airflow 3.x strictly coordinates scheduling, dependency management, and quality assertions.

```mermaid
flowchart TD
    subgraph Auth["OAuth 2.0 Auth Side-Flow"]
        Operator["Operator Setup<br/>(One-Time Interactive)"] -->|Auth Code Consent| SpotifyAuth["Spotify Accounts Service"]
        SpotifyAuth -->|Refresh Token| SecMgr[("AWS Secrets Manager<br/>(spotify/api/credentials)")]
    end

    subgraph Sources["1. Source Layer"]
        API["Spotify Web API<br/>(/v1/playlists/{id}/items)"]
    end

    subgraph Lake["2. AWS Data Lake (us-east-1)"]
        Lambda["AWS Lambda Extractor<br/>(Python 3.12, Dynamic Token Refresh)"]
        S3Bronze[("Amazon S3 Bronze<br/>• Raw JSON Payloads<br/>• Immutable / Replayable<br/>• Partitioned by date & run_id")]
        Glue["AWS Glue 5.1 / PySpark 3.5.6<br/>• Schema Enforcement<br/>• Item Type Validation<br/>• Explode Arrays & Deduplicate"]
        S3Silver[("Amazon S3 Silver<br/>• Curated Parquet<br/>• Snappy Compressed<br/>• Partitioned by date")]
    end

    subgraph Warehouse["3. Snowflake Analytical Warehouse"]
        SQS["Amazon SQS / S3 Events"]
        Snowpipe["Snowpipe Continuous Ingestion<br/>(Capturing Lineage Metadata)"]
        Landing[("LANDING Schema<br/>• 1:1 Parquet Relational Tables")]
        dbt["dbt Core Engine<br/>• Staging Views<br/>• Dimensional Star Schema<br/>• Incremental Merge Marts"]
        Core[("CORE & MARTS Schemas<br/>• dim_track, dim_artist, dim_album<br/>• bridge_track_artist<br/>• fact_playlist_snapshot")]
    end

    subgraph Serving["4. Serving"]
        BIConsumer["Consumption-ready MARTS views<br/>(BI tool optional / deferred)"]
    end

    subgraph Orchestration["Airflow 3.x Orchestration (Local / Docker)"]
        Airflow["Apache Airflow 3.x<br/>• Task SDK Coordinator<br/>• External Task Sensors<br/>• Deadline Alerts & Quality Gates"]
    end

    subgraph Foundation["Cross-Cutting Platform Governance"]
        TF["Terraform (IaC)"]
        GHA["GitHub Actions (CI/CD)"]
        CW["CloudWatch & Audit Telemetry"]
        Sec["AWS Secrets Manager & RBAC"]
    end

    %% Data Pipeline Flow
    SecMgr -.->|Fetch Token| Lambda
    Lambda -->|Token Exchange & GET| API
    API -->|"HTTPS JSON (50/page)"| Lambda
    Lambda -->|PutObject| S3Bronze
    S3Bronze -->|Read Payloads| Glue
    Glue -->|Write Parquet| S3Silver
    S3Silver -->|S3 Event| SQS
    SQS -->|Notify| Snowpipe
    Snowpipe -->|Copy Into| Landing
    Landing -->|Transform| dbt
    dbt -->|Incremental Merge| Core
    Core -->|Query| BIConsumer

    %% Orchestration
    Airflow -.->|1. Trigger| Lambda
    Airflow -.->|2. Trigger| Glue
    Airflow -.->|3. Validate| Landing
    Airflow -.->|4. Execute| dbt
```

---

## 2. Business & Analytical Problem

Music streaming metadata undergoes continuous changes as tracks enter, shift positions, and exit playlists. However, typical educational ETL pipelines suffer from fundamental design flaws:
- **State Overwriting**: Overwriting playlist state daily destroys historical track movements.
- **Missing Retention Metrics**: Unable to calculate how many consecutive days a track stays on a playlist.
- **Unverified API Assumptions**: Relying on deprecated endpoints (`/tracks`) or removed popularity fields.

### What This Platform Answers
By persisting immutable daily snapshots of **monitored user-owned or collaborative playlists accessible under authorized Spotify application scopes**, this platform provides deep longitudinal analysis:
1. **Track Lifecycle & Churn**: Exact entry date, exit date, and retention tenure (days present).
2. **Positional Dynamics**: Daily rank movement, best position achieved, and average position.
3. **Artist Representation & Concentration**: Which artists occupy the greatest playlist share over time.
4. **Playlist Volatility**: Quantifying turnover rates (daily additions vs. exits) across monitored playlists.
5. **Catalog Composition Trends**: Longitudinal evolution of explicit content share, duration distribution, and release recency.

---

## 3. Technology Stack

| Layer | Technology | Architectural Rationale |
| :--- | :--- | :--- |
| **Language** | Python 3.12 | Modern runtime, native typing, robust SDKs (`boto3`, `requests`). |
| **Authentication** | OAuth 2.0 Auth Code + Refresh Token | Complies with 2026 Spotify Development Mode restrictions for user-scoped playlist access. |
| **Orchestration** | Apache Airflow 3.x | Task SDK (`airflow.sdk`) authoring, service-oriented execution, and Deadline Alerts. |
| **Extraction** | AWS Lambda | Serverless extractor runtime implemented; real cloud duration and cost remain unmeasured until deployment. |
| **Data Lake** | Amazon S3 | Tiered storage: raw immutable JSON in Bronze, columnar Snappy-compressed Parquet in Silver. |
| **Lake Processing** | AWS Glue 5.1 / PySpark | Managed Spark 3.5.6 / Python 3.11 for unnesting semi-structured items and schema enforcement. |
| **Ingestion** | Snowflake Snowpipe | Serverless, continuous micro-batch loading from S3 into Landing tables with file audit metadata. |
| **Data Warehouse** | Snowflake | Columnar analytical warehouse with `X-Small` warehouse and 60-second auto-suspend. |
| **Transformation** | dbt Core | SQL dimensional modeling, surrogate key hashing, incremental `MERGE`, and data testing. |
| **Infrastructure as Code** | Terraform | Version-controlled AWS resource definitions with offline validation and security scanning; Snowflake DDL remains version-controlled separately. |
| **CI/CD** | GitHub Actions | Python lint/test, Glue-parity Spark contracts, Snowflake SQL contracts, and dbt parse/manifest validation on PRs and `main`. |
| **Serving** | Snowflake MARTS / `BI_*` views | Consumption-ready analytical contract validated with `SPOTIFY_ANALYST`; Power BI remains an optional downstream consumer outside v1.0.0. |

---

## 4. Key Architectural Decisions

The platform's engineering design is formalized through **Architecture Decision Records (ADRs)** in [`docs/adr/`](docs/adr/):

- **[ADR-0001: Airflow as Orchestrator, Not Execution Engine](docs/adr/0001-airflow-as-orchestrator.md)**: Airflow never processes data in worker memory. Compute is delegated to Lambda, Glue 5.1, and Snowflake.
- **[ADR-0002: S3 Bronze as Durable Immutable Landing Layer](docs/adr/0002-s3-as-durable-landing-zone.md)**: Preserves raw API responses under deterministic partitions (`ingestion_date=YYYY-MM-DD/run_id=<id>/`) enabling full replayability.
- **[ADR-0003: Apache Parquet for Curated Data](docs/adr/0003-parquet-for-curated-data.md)**: Snappy-compressed columnar format provides up to 75% storage savings and accelerates warehouse loading.
- **[ADR-0004: Snowflake as Central Analytical Warehouse](docs/adr/0004-snowflake-as-analytical-warehouse.md)**: Elastic compute scaling with automated 60-second auto-suspension to strictly control costs.
- **[ADR-0005: Separate Spark and dbt Responsibilities](docs/adr/0005-separate-spark-and-dbt-responsibilities.md)**: Spark handles semi-structured array explosion; dbt handles modular SQL dimensional modeling.
- **[ADR-0006: Historical Playlist Snapshots](docs/adr/0006-historical-playlist-snapshots.md)**: Pinned to canonical daily grain `(playlist_id + snapshot_date + track_position)` with `spotify_snapshot_id` lineage.
- **[ADR-0007: Spotify Authorization Code & Refresh Token](docs/adr/0007-spotify-authorization-code-and-refresh-token.md)**: Replaces Client Credentials with two-phase Auth Code + stored refresh token for scheduled ingestion.
- **[ADR-0008: Synthetic Analytics and Source Use Boundary](docs/adr/0008-synthetic-analytics-and-source-use-boundary.md)**: Original conservative portfolio boundary; superseded for the current demo by ADR-0009 while its live-source governance rule remains in force.
- **[ADR-0009: CC0 Source Metadata with Synthetic Temporal Demo](docs/adr/0009-cc0-source-with-synthetic-temporal-demo.md)**: Uses a CC0 playlist corpus for reproducible source metadata while keeping all longitudinal change behavior synthetic and explicitly labeled.

---

## 5. Spark vs. dbt Responsibilities

```
Raw JSON (Bronze S3)
       │
       ▼ [AWS Glue 5.1 / PySpark 3.5.6] -> Parse items, validate tracks, explode artists
Curated Parquet (Silver S3)
       │
       ▼ [Snowpipe] -> Automated Ingestion + Metadata Lineage
Landing Tables (Snowflake)
       │
       ▼ [dbt Core] -> Dimensional Modeling & Incremental Merge
Core Star Schema & Marts (Snowflake)
```

- **AWS Glue 5.1 / PySpark**: Unpacks raw JSON items, validates item types, enforces explicit StructType schemas, handles technical deduplication, and serializes Snappy Parquet.
- **dbt Core**: Generates surrogate keys, maintains dimensions (`dim_track`, `dim_artist`, `dim_album`), manages `bridge_track_artist`, merges `fact_playlist_snapshot` on `snapshot_pk`, and builds analytical marts.

---

## 6. Planned Snowflake Dimensional Model

```mermaid
erDiagram
    dim_track ||--o{ bridge_track_artist : "has"
    dim_artist ||--o{ bridge_track_artist : "credited"
    dim_album ||--o{ dim_track : "contains"
    dim_track ||--o{ fact_playlist_snapshot : "observed at slot"
    dim_playlist ||--o{ fact_playlist_snapshot : "hosts slot"

    dim_track {
        string track_pk PK
        string track_id "Natural key"
        string track_name
        int duration_ms
        boolean is_explicit
    }

    dim_artist {
        string artist_pk PK
        string artist_id "Natural key"
        string artist_name
    }

    dim_album {
        string album_pk PK
        string album_id "Natural key"
        string album_name
        date release_date
        int total_tracks
    }

    dim_playlist {
        string playlist_pk PK
        string playlist_id "Natural key"
        string playlist_name
    }

    bridge_track_artist {
        string bridge_pk PK
        string track_pk FK
        string artist_pk FK
        int artist_order
    }

    fact_playlist_snapshot {
        string snapshot_pk PK
        string playlist_pk FK
        string track_pk FK
        date snapshot_date
        int track_position
        string spotify_snapshot_id
        timestamp snapshot_timestamp
        timestamp added_at
        string pipeline_run_id
    }
```

Detailed schema definitions, canonical grain evaluations, and data dictionaries are documented in [`docs/DATA_MODEL.md`](docs/DATA_MODEL.md).

---

## 7. Cost Governance ($20/Month Portfolio Budget Target)

The **USD 20/month** figure is an operational planning target, not a guaranteed
provider-side spending cap. The validated slice now has live guardrails on both providers,
while exact per-run dollar attribution still depends on provider billing/metering windows.

| Metric | Budget Target | Governance Type | Notes |
| :--- | :--- | :--- | :--- |
| **Monthly Target** | **≤ $20.00 USD / month** | Planning target | A manual AWS Budget is deployed at $5/month for this demo; M8 will codify budget automation. Snowflake uses a deployed 2-credit monthly resource monitor. |
| **Idle Cost** | No always-on warehouse compute | Operational control | `COMPUTE_WH` is X-Small with 60-second auto-suspend and was explicitly suspended after validation. Provider-side idle billing statements are not yet isolated. |
| **Validation Usage** | Measured usage, not isolated dollar cost | Evidence | The four successful Airflow-orchestrated Glue runs reported 589 total DPU-seconds. The Snowflake resource monitor reported 0.45 cumulative credits used since monitor creation after the final orchestration/replay validation. |

Key cost control mechanisms:
- **Snowflake**: `COMPUTE_WH` is deployed as `X-Small` with `AUTO_SUSPEND = 60` and the bounded development resource monitor attached.
- **Airflow**: Target design keeps Airflow local rather than provisioning MWAA.
- **Log Retention**: Seven-day CloudWatch retention is a target for the Terraform phase, not a deployed control today.
- **Teardown**: Terraform-based teardown is planned in M8 and must be verified against actual provisioned resources and billing state.

Full budget breakdown available in [`docs/COST_STRATEGY.md`](docs/COST_STRATEGY.md).

---

## 8. Repository Structure

```
.
├── .github/
│   ├── ISSUE_TEMPLATE/       # Structured GitHub issue templates (bug & feature)
│   ├── workflows/            # GitHub Actions CI pipeline
│   └── pull_request_template.md
│
├── docs/                     # Comprehensive engineering documentation
│   ├── PROJECT_BLUEPRINT.md  # Master technical specification and architectural baseline
│   ├── COST_STRATEGY.md      # Budget limits, cost drivers, and teardown runbook
│   ├── ARCHITECTURE.md       # High-level architecture and sequence diagrams
│   ├── DATA_MODEL.md         # Schema dictionaries, dimensional model, canonical keys
│   ├── SECURITY.md           # OAuth 2.0 token lifecycle, IAM least privilege, RBAC
│   ├── OBSERVABILITY.md      # Structured telemetry schema (pipeline_run_id & snapshot_id)
│   ├── RUNBOOK.md            # Incident triage, replay and audit procedures
│   ├── INTERVIEW_GUIDE.md    # Technical talking points for portfolio review
│   ├── DEMO_GUIDE.md         # Short reproducible portfolio walkthrough
│   ├── REFERENCES.md         # Official 2026 API, Glue 5.1, and Airflow 3 citations
│   └── adr/                  # Architectural Decision Records (ADR 0001 - 0008)
│
├── src/
│   └── spotify_data_platform/# Core Python package
│
├── tests/                    # Unit/integration, Spark, Snowflake-contract, and dbt-contract suites
│
├── airflow/                  # Airflow 3.x DAGs, Docker Compose, and Task SDK
├── lambda/                   # Serverless Spotify API extractor handler
├── glue/                     # AWS Glue 5.1 PySpark scripts and explicit schemas
├── dbt/                      # dbt Core project (staging, core, marts, tests)
├── snowflake/                # Snowflake DDL, Snowpipe, and RBAC manifests
├── infra/terraform/          # Versioned AWS IaC modules and budget/monitoring guardrails
├── powerbi/                  # Deferred optional consumer notes (not part of v1.0.0)
├── scripts/                  # Developer utilities and mock data generators
│
├── .editorconfig             # Standardized cross-editor formatting rules
├── .env.example              # Template environment variables (no credentials)
├── .geminiignore             # Gemini CLI security and noise filters
├── .gitignore                # Git exclusion rules
├── BACKLOG.md                # Phased engineering roadmap across milestones M0 - M9
├── CONTRIBUTING.md           # Contribution guidelines, branching, and commit conventions
├── GEMINI.md                 # Repository-level Gemini CLI operational guidelines
├── LICENSE                   # MIT Open Source License
├── Makefile                  # Local automation commands (lint, test, format, check)
├── pyproject.toml            # Python packaging and tool configuration (Ruff, pytest)
└── README.md
```

---

## 9. Local Development Setup

### Prerequisites
- Python 3.12+ (managed via `pyenv` or `asdf`)
- Git & GitHub CLI (`gh`)
- Docker & Docker Compose for the local Airflow 3 orchestration runtime
- Python 3.11 + Java 17 for the Glue 5.1 parity test environment (`make spark-test`)

### Quick Start
1. **Clone the repository**:
   ```bash
   git clone https://github.com/DanielBBrasileiro/spotify-analytics-data-platform.git
   cd spotify-analytics-data-platform
   ```

2. **Initialize virtual environment & install dev dependencies**:
   ```bash
   make setup
   ```

3. **Optional integration configuration** (not needed for offline tests):
   ```bash
   cp .env.example .env
   # The application reads process environment; do not commit real credentials.
   ```

4. **Run static analysis and tests**:
   ```bash
   make check
   ```

### Makefile Commands
- `make setup`: Creates `.venv` and installs dependencies in editable mode with development packages.
- `make lint`: Runs Ruff linter (`ruff check .`).
- `make format`: Formats code using Ruff (`ruff format .`).
- `make format-check`: Verifies code formatting without writing changes.
- `make test`: Runs unit tests via `pytest`.
- `make check`: Executes `lint`, `format-check`, and `test` sequentially.
- `make clean`: Removes Python build artifacts, `.pyc` files, and test caches.

---

## 10. Phased Implementation Roadmap

- [x] **Milestone M0 — Project Foundation & Architecture Blueprint** (Completed & Revised in v0.1.1)
- [x] **Milestone M1 — Local Spotify Ingestion** (Auth Code client, pagination, fixtures/parser tests, run metadata, local Bronze persistence)
- [x] **Milestone M2 — AWS Lambda & Bronze Data Lake** (runtime/contracts complete; deployment awaits cloud infrastructure)
- [x] **Milestone M3 — Glue / PySpark & Silver Layer** (offline complete on Glue 5.1 parity runtime)
- [x] **Milestone M4 — Snowflake & Snowpipe** (bounded manual cloud slice validated; Terraform remains M8)
- [x] **Milestone M5 — dbt Analytics Engineering** (bounded cloud build, serving views and selective replay validated live)
- [x] **Milestone M6 — Airflow Orchestration** (bounded live orchestration validated with Task SDK, retries, rescheduling sensors, Deadline Alert and structured failure callbacks; live Spotify Lambda invocation is a separate source-path extension)
- [x] **Milestone M7 — Data Quality & Observability** (cross-tier gates, unified run reports, replay/audit CLIs and incident runbooks)
- [x] **Milestone M8 — Terraform & CI/CD Hardening** (AWS IaC, static security/lint checks and budget definitions; existing manually deployed resources were not replaced in-place)
- [x] **Milestone M9 — Serving & Portfolio Release** (live-validated `BI_*` serving views, interview/demo documentation and v1.0.0 packaging; Power BI explicitly deferred)

Refer to [BACKLOG.md](BACKLOG.md) for detailed issues, user stories, and acceptance criteria.

---

## 11. License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

## Current execution and serving handoff

The next integrated path uses the existing CC0 demo, the local
[Airflow DAG](airflow/README.md), exact run-scoped Landing checks, and `dbt build`.
Four `BI_*` views expose names, one-based positions, documented units and synthetic-data
labels to future consumers. See the [serving contract](docs/SERVING_CONTRACT.md).
No Power BI dashboard, `.pbit`, or DAX artifact is part of v1.0.0. The repository stops at a tested serving contract so a BI tool can be attached without changing pipeline semantics.

The bounded Airflow smoke run and one-day replay completed successfully against AWS Glue,
Snowpipe and Snowflake. The four `BI_*` views were queried successfully using the
`SPOTIFY_ANALYST` role after the run. Power BI artifacts remain intentionally deferred.
