# Spotify Analytics Data Platform

[![CI](https://github.com/DanielBBrasileiro/spotify-analytics-data-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/DanielBBrasileiro/spotify-analytics-data-platform/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

> Production-oriented data engineering platform that ingests historical Spotify playlist snapshots using AWS Lambda, S3, Glue/PySpark, Snowflake, dbt Core, and Apache Airflow, with infrastructure as code, CI/CD, cross-tier data quality, and business intelligence in Power BI.

---

### Project Status: Foundation / Architecture Phase
> **Notice**: This repository is in **Milestone M0 (Project Foundation / Architecture Blueprint)**. The architecture, data models, infrastructure definitions, CI workflows, and decision records are established. Pipeline components are scheduled for incremental implementation across Milestones M1 through M9 per [BACKLOG.md](BACKLOG.md). Live cloud resources are deliberately not provisioned in this foundation phase to prevent unbudgeted cloud expenditure.

---

## 1. Architecture Overview

The platform implements a decoupled, lakehouse-to-warehouse architecture where compute workloads are delegated to specialized engines while Apache Airflow strictly coordinates scheduling, dependency management, and quality assertions.

```mermaid
flowchart TD
    subgraph Sources["1. Source Layer"]
        API["Spotify Web API<br/>(OAuth 2.0 Client Credentials)"]
    end

    subgraph Lake["2. AWS Data Lake (us-east-1)"]
        Lambda["AWS Lambda Extractor<br/>(Python 3.12, Secrets Manager)"]
        S3Bronze[("Amazon S3 Bronze<br/>• Raw JSON Payloads<br/>• Immutable / Replayable<br/>• Partitioned by date & run_id")]
        Glue["AWS Glue 4.0 / PySpark<br/>• Schema Enforcement<br/>• Explode Nested Arrays<br/>• Technical Deduplication"]
        S3Silver[("Amazon S3 Silver<br/>• Curated Parquet<br/>• Snappy Compressed<br/>• Partitioned by date")]
    end

    subgraph Warehouse["3. Snowflake Analytical Warehouse"]
        SQS["Amazon SQS / S3 Events"]
        Snowpipe["Snowpipe Continuous Ingestion<br/>(Auto-Ingest)"]
        Landing[("LANDING Schema<br/>• 1:1 Parquet Relational Tables")]
        dbt["dbt Core Engine<br/>• Staging Views<br/>• Dimensional Star Schema<br/>• Analytical Marts"]
        Core[("CORE & MARTS Schemas<br/>• dim_track, dim_artist, dim_album<br/>• bridge_track_artist<br/>• fact_playlist_snapshot")]
    end

    subgraph Serving["4. Serving & BI"]
        PowerBI["Power BI Analytical Dashboard<br/>(DirectQuery / Import)"]
    end

    subgraph Orchestration["Airflow Orchestration Layer (Local / Docker)"]
        Airflow["Apache Airflow 2.x<br/>• Schedule Coordinator<br/>• External Task Sensors<br/>• Cross-Tier Quality Gates"]
    end

    subgraph Foundation["Cross-Cutting Platform Governance"]
        TF["Terraform (IaC)"]
        GHA["GitHub Actions (CI/CD)"]
        CW["CloudWatch & Audit Telemetry"]
        Sec["AWS Secrets Manager & RBAC"]
    end

    %% Data Pipeline Flow
    API -->|HTTPS JSON| Lambda
    Lambda -->|PutObject| S3Bronze
    S3Bronze -->|Read Payloads| Glue
    Glue -->|Write Parquet| S3Silver
    S3Silver -->|S3 Event| SQS
    SQS -->|Notify| Snowpipe
    Snowpipe -->|Copy Into| Landing
    Landing -->|Transform| dbt
    dbt -->|Materialize| Core
    Core -->|Query| PowerBI

    %% Orchestration
    Airflow -.->|1. Trigger| Lambda
    Airflow -.->|2. Trigger| Glue
    Airflow -.->|3. Validate| Landing
    Airflow -.->|4. Execute| dbt
```

---

## 2. Business & Analytical Problem

Music streaming platforms operate in a dynamic ecosystem where editorial and algorithmic playlists dictate artist visibility and commercial success. However, typical educational ETL tutorials suffer from severe analytical limitations:
- **State Overwriting**: They overwrite playlist state daily, discarding historical track movements.
- **Inability to Track Churn**: They cannot answer which tracks entered or left a playlist between dates.
- **Missing Retention Metrics**: They cannot compute how long an artist or track remains on a major chart.

### What This Platform Answers
By persisting immutable daily snapshots and modeling track positions over time, this platform enables deep longitudinal analysis:
1. **Track Lifecycle & Churn**: Exact entry date, exit date, and retention tenure (in days) on monitored playlists.
2. **Artist Market Dominance**: Tracking which artists and labels sustain multi-track presence over months.
3. **Playlist Volatility Index**: Quantifying turnover rates between stable editorial playlists and high-churn discovery playlists.
4. **Popularity Trajectory**: Correlating playlist placement with changes in Spotify's internal popularity index.

---

## 3. Technology Stack

| Layer | Technology | Architectural Rationale |
| :--- | :--- | :--- |
| **Language** | Python 3.12 | Modern runtime, native type hinting, performance optimizations, robust SDKs (`boto3`, `requests`). |
| **Orchestration** | Apache Airflow 2.x | Enterprise standard for workflow dependency graphs, retry mechanisms, and cross-system task sequencing. |
| **Extraction** | AWS Lambda | Ephemeral serverless execution (< 60s); eliminates idle server costs. |
| **Data Lake** | Amazon S3 | Tiered storage: raw immutable JSON in Bronze, columnar Snappy-compressed Parquet in Silver. |
| **Lake Processing** | AWS Glue / PySpark | Distributed engine for exploding nested JSON arrays, schema enforcement, and deduplication at low DPU-hour cost. |
| **Ingestion** | Snowflake Snowpipe | Serverless, event-driven continuous micro-batch loading from S3 into warehouse landing tables. |
| **Data Warehouse** | Snowflake | Micro-partitioned cloud warehouse with per-second billing and 60-second auto-suspend. |
| **Transformation** | dbt Core | In-warehouse SQL dimensional modeling, surrogate key hashing, data testing, and automated lineage. |
| **Infrastructure as Code** | Terraform | Reproducible, version-controlled cloud infrastructure across AWS and Snowflake. |
| **CI/CD** | GitHub Actions | Automated linting (`ruff`), code formatting checks, and unit testing (`pytest`) on every PR. |
| **Business Intelligence** | Power BI | Star schema analytical reporting, interactive churn dashboards, and executive metrics. |

---

## 4. Key Architectural Decisions

The platform's engineering design is formalized through **Architecture Decision Records (ADRs)** located in [`docs/adr/`](docs/adr/):

- **[ADR-0001: Airflow as Orchestrator, Not Execution Engine](docs/adr/0001-airflow-as-orchestrator.md)**: Airflow never processes data in worker memory. Compute is delegated to Lambda, Glue, and Snowflake.
- **[ADR-0002: S3 Bronze as Durable Immutable Landing Layer](docs/adr/0002-s3-as-durable-landing-zone.md)**: Preserves raw API responses under deterministic partitions (`ingestion_date=YYYY-MM-DD/run_id=<id>/`) enabling full pipeline replayability.
- **[ADR-0003: Apache Parquet for Curated Data](docs/adr/0003-parquet-for-curated-data.md)**: Snappy-compressed columnar format provides up to 75% storage savings and accelerates warehouse loading.
- **[ADR-0004: Snowflake as Central Analytical Warehouse](docs/adr/0004-snowflake-as-analytical-warehouse.md)**: Elastic compute scaling with automated 60-second auto-suspension to strictly control costs.
- **[ADR-0005: Separate Spark and dbt Responsibilities](docs/adr/0005-separate-spark-and-dbt-responsibilities.md)**: Spark handles complex semi-structured array explosion; dbt handles modular SQL dimensional modeling.
- **[ADR-0006: Historical Playlist Snapshots](docs/adr/0006-historical-playlist-snapshots.md)**: Models playlist membership as point-in-time snapshot facts rather than destructive in-place updates.

---

## 5. Spark vs. dbt Responsibilities

A common architectural trap is attempting to use either Spark or dbt for everything. This platform enforces a clean boundary:

```
Raw JSON (Bronze S3)
       │
       ▼ [AWS Glue / PySpark] -> Heavy JSON Parsing & Normalization
Curated Parquet (Silver S3)
       │
       ▼ [Snowpipe] -> Automated Ingestion
Landing Tables (Snowflake)
       │
       ▼ [dbt Core] -> Dimensional Modeling & Business Logic
Core Star Schema & Marts (Snowflake)
```

- **AWS Glue / PySpark**: Unpacks raw JSON arrays, enforces explicit StructType schemas, handles technical deduplication, and serializes Snappy Parquet.
- **dbt Core**: Generates surrogate keys, maintains dimensional tables (`dim_track`, `dim_artist`, `dim_album`), manages many-to-many bridge relationships, increments snapshot facts, and builds analytical marts.

---

## 6. Planned Snowflake Dimensional Model

```mermaid
erDiagram
    dim_track ||--o{ bridge_track_artist : "has"
    dim_artist ||--o{ bridge_track_artist : "credited"
    dim_album ||--o{ dim_track : "contains"
    dim_track ||--o{ fact_playlist_snapshot : "member"
    dim_playlist ||--o{ fact_playlist_snapshot : "contains"

    dim_track {
        string track_pk PK
        string track_id NK
        string track_name
        int duration_ms
        boolean is_explicit
        int popularity
    }

    dim_artist {
        string artist_pk PK
        string artist_id NK
        string artist_name
        string primary_genre
    }

    dim_album {
        string album_pk PK
        string album_id NK
        string album_name
        date release_date
        int total_tracks
    }

    dim_playlist {
        string playlist_pk PK
        string playlist_id NK
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
        timestamp added_at
        string pipeline_run_id
    }
```

Detailed schema definitions, natural key evaluations, and data dictionaries are documented in [`docs/DATA_MODEL.md`](docs/DATA_MODEL.md).

---

## 7. Cost Governance ($20/Month Portfolio Budget)

To ensure this portfolio project can be run and demonstrated economically, the architecture operates under a strict budget ceiling:

| Metric | Budget Target | Strategy |
| :--- | :--- | :--- |
| **Monthly Ceiling** | **≤ $20.00 USD / month** | Managed via AWS Budgets and Snowflake Resource Monitors. |
| **Idle Cost** | **$0.00 / month** | Zero always-on EC2 instances, EMR clusters, or NAT Gateways. |
| **Single Run Cost** | **< $0.25 USD / run** | Ephemeral Lambda (< 15s), Glue job (~2 min), Snowflake `X-Small` warehouse. |

Key cost control mechanisms:
- **Snowflake**: Virtual warehouse configured as `X-Small` with `AUTO_SUSPEND = 60` seconds.
- **Airflow**: Runs locally in Docker Compose during development, eliminating AWS MWAA fees (~$350/month).
- **Log Retention**: CloudWatch logs expire after 7 days.
- **Teardown**: All cloud resources are managed via Terraform and can be destroyed instantly (`terraform destroy`).

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
│   ├── PROJECT_BLUEPRINT.md  # Authoritative 47-section master design specification
│   ├── COST_STRATEGY.md      # Budget limits, cost drivers, and teardown runbook
│   ├── ARCHITECTURE.md       # High-level architecture and sequence diagrams
│   ├── DATA_MODEL.md         # Schema dictionaries, dimensional model, natural keys
│   ├── SECURITY.md           # Zero secrets policy, IAM least privilege, RBAC
│   ├── OBSERVABILITY.md      # Structured telemetry schema and auditing queries
│   ├── RUNBOOK.md            # Incident triage playbooks and backfill procedures
│   ├── REFERENCES.md         # Attribution, citations, and official documentation
│   └── adr/                  # Architectural Decision Records (ADR 0001 - 0006)
│
├── src/
│   └── spotify_data_platform/# Core Python package
│
├── tests/
│   └── unit/                 # Unit test suite (pytest)
│
├── airflow/                  # Airflow DAGs, Docker Compose, and custom operators
├── lambda/                   # Serverless Spotify API extractor handler
├── glue/                     # PySpark transformation scripts and explicit schemas
├── dbt/                      # dbt Core project (staging, core, marts, tests)
├── snowflake/                # Snowflake DDL, Snowpipe, and RBAC manifests
├── infra/terraform/          # Infrastructure as Code modules (S3, IAM, Lambda, Glue)
├── powerbi/                  # Semantic models, DAX measures, and dashboard templates
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
- Docker & Docker Compose (for local Airflow)

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

3. **Configure local environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your local non-production placeholders
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

- [x] **Milestone M0 — Project Foundation & Architecture Blueprint** (Current)
- [ ] **Milestone M1 — Local Spotify Ingestion** (OAuth client, pagination, mock fixtures, parser tests)
- [ ] **Milestone M2 — AWS Lambda & Bronze Data Lake** (Serverless extractor, S3 Bronze, Secrets Manager)
- [ ] **Milestone M3 — Glue / PySpark & Silver Layer** (StructType schemas, array explosion, Parquet Silver)
- [ ] **Milestone M4 — Snowflake & Snowpipe** (Storage integration, Snowpipe auto-ingest, Landing tables)
- [ ] **Milestone M5 — dbt Analytics Engineering** (Staging models, Kimball star schema, marts, dbt tests)
- [ ] **Milestone M6 — Airflow Orchestration** (Docker Airflow, DAG coordination, external operators)
- [ ] **Milestone M7 — Data Quality & Observability** (Quality gates, run telemetry, incident playbooks)
- [ ] **Milestone M8 — Terraform & CI/CD Hardening** (AWS IaC modules, CI security, AWS Budgets)
- [ ] **Milestone M9 — Power BI & Portfolio Release** (Semantic model, dashboard visuals, v1.0.0 release)

Refer to [BACKLOG.md](BACKLOG.md) for detailed issues, user stories, and acceptance criteria.

---

## 11. License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
