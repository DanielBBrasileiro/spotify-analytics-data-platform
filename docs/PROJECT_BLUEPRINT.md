# Spotify Analytics Data Platform — Master Project Blueprint

**Release:** v1.0.0

**Status:** Portfolio release complete; bounded AWS/Snowflake path live-validated

**Primary region:** AWS `us-east-1`
**Core stack:** Python 3.12 · Airflow 3.2.2 · S3 · Glue 5.1 / Spark 3.5.6 · Snowflake · Snowpipe · dbt Core 1.12 · Terraform · GitHub Actions

This blueprint is the high-level project charter for the released platform. Detailed runtime contracts live in the specialized documents linked throughout this file; this document intentionally avoids duplicating every field-level or operational rule.

---

## 1. Executive Intent

The Spotify Analytics Data Platform demonstrates a modern batch data engineering architecture for preserving historical playlist snapshots and converting them into replayable analytical data.

Its engineering value is not the Spotify theme itself. The portfolio focuses on the platform concerns that transfer to production data systems:

- immutable source landing;
- physical vs logical lineage;
- distributed technical curation;
- event-driven warehouse ingestion;
- dimensional modeling and incremental merge;
- exact cross-tier quality gates;
- external-service orchestration;
- safe retries and replay;
- evidence-driven observability;
- Infrastructure as Code and CI security checks;
- explicit cost governance;
- documented consumer contracts.

The public demo deliberately uses a **CC0-backed source corpus with synthetic temporal evolution** so the downstream engineering path is reproducible without claiming real Spotify history.

---

## 2. Evidence Boundary

The release distinguishes four states rather than collapsing everything into “implemented”.

| Status | Meaning in this repository |
|---|---|
| **Live validated** | Exercised against the bounded AWS/Snowflake demo path. |
| **Implemented + contract validated** | Code exists and automated contracts pass, but it was not part of the final bounded live slice. |
| **Offline IaC validated** | Terraform/static contracts pass without claiming live state ownership. |
| **Deferred** | Intentionally outside v1.0.0. |

### Live-validated bounded path

```text
CC0-backed snapshots
      ↓
S3 Bronze
      ↓
Glue 5.1 / Spark 3.5.6
      ↓
S3 Silver / Parquet
      ↓
Snowpipe → Snowflake LANDING
      ↓
dbt STAGING → CORE → MARTS → BI_* views
      ↑
Airflow 3.2.2 / Docker coordinates the external boundaries
```

### Implemented but separate source path

```text
Spotify Web API → AWS Lambda / Python 3.12 → S3 Bronze
```

The live Spotify path is not presented as part of the final bounded demo unless separate source-side evidence is captured.

### Deferred consumer scope

Power BI semantic modeling, DAX, `.pbit` artifacts and dashboards are not part of v1.0.0. The released data-engineering contract ends at tested Snowflake serving views.

---

## 3. Architecture

For the detailed diagram and component boundaries, see [`ARCHITECTURE.md`](ARCHITECTURE.md).

The platform follows five core separation rules:

1. **Airflow coordinates; external engines compute.**
2. **Bronze preserves source shape; Silver enforces technical structure.**
3. **Snowpipe loads physical data; dbt owns analytical semantics.**
4. **Physical attempts are immutable; logical facts converge idempotently.**
5. **Consumer semantics live in version-controlled Snowflake/dbt models, not a dashboard file.**

---

## 4. Platform Objectives

### 4.1 Historical analytical capability

Support longitudinal playlist analysis such as:

- observed track entry/exit behavior;
- retention streaks and cumulative observed days;
- playlist turnover;
- position movement;
- artist presence and playlist reach;
- playlist composition changes across observed snapshots.

For the public CC0 demo, those temporal behaviors are **deterministically synthetic scenarios**, not observed Spotify market behavior.

### 4.2 Replayable engineering

Allow a logical date to be reprocessed without destroying previous physical evidence and without inflating the canonical warehouse fact.

### 4.3 Low-cost cloud demonstration

Exercise real managed services where they add portfolio value while avoiding always-on infrastructure that does not improve the engineering story.

### 4.4 Reproducible validation

Keep the default developer/CI path credential-free and offline where possible; make live cloud runs explicit and bounded.

### 4.5 Honest public presentation

Document what was exercised, what was only contract-tested, and what was deferred.

---

## 5. Non-Goals

v1.0.0 does not aim to provide:

- real-time Kafka/Kinesis streaming;
- arbitrary scraping of public Spotify playlists;
- managed Airflow/MWAA;
- multi-region HA or production commercial SLOs;
- 24/7 pager/on-call integration;
- Kubernetes, EMR or Databricks simply for stack breadth;
- Power BI implementation;
- a Terraform apply/destroy demonstration against the pre-existing validated cloud slice;
- claims that synthetic CC0 temporal behavior represents real Spotify history.

---

## 6. Data Flow

### 6.1 Bounded validated demo

1. Airflow validates a bounded date window and creates one physical UUID v4 `pipeline_run_id` per planned snapshot record.
2. The CC0-generated source-shaped payload is uploaded immutably to run-scoped S3 Bronze.
3. Airflow submits one Glue 5.1 job for that physical attempt.
4. Spark enforces technical schemas and writes six Silver Parquet datasets.
5. Glue publishes a completion manifest inventorying exact files and row counts.
6. S3 notifications drive Snowpipe ingestion into Snowflake Landing.
7. Airflow reconciles exact Landing filenames, row counts and file-row uniqueness against the completion manifest.
8. Only after all mapped readiness gates pass does dbt build STAGING, CORE, MARTS and `BI_*` views.
9. The reporting path persists final run evidence and can generate a unified pipeline run report.

### 6.2 Optional live-source path

The Spotify source client uses Authorization Code + refresh token, paginates playlist items, verifies source snapshot consistency and can execute behind the Lambda runtime adapter. A successful live source path would converge on the same Bronze contract as the bounded demo.

See [`LOCAL_INGESTION.md`](LOCAL_INGESTION.md).

---

## 7. Identity Model

The platform intentionally uses different identifiers for different concerns.

| Identifier | Responsibility |
|---|---|
| `airflow_run_id` | One orchestration execution. |
| `pipeline_run_id` | One physical snapshot-processing attempt; UUID v4. |
| `spotify_snapshot_id` | Source version identity or explicitly simulated demo version. |
| `snapshot_date` | Logical business observation date. |

The canonical fact grain is:

```text
(playlist_id, snapshot_date, track_position)
```

This separation is central to replay idempotency. See [`DATA_MODEL.md`](DATA_MODEL.md).

---

## 8. Data Lake Contract

The AWS design uses one private lake bucket with explicit prefixes:

```text
s3://<lake>/
├── bronze/
│   └── spotify/playlist_tracks/
│       └── ingestion_date=YYYY-MM-DD/
│           └── run_id=<pipeline_run_id>/
├── silver/
│   └── <dataset>/
│       └── ingestion_date=YYYY-MM-DD/
│           └── run_id=<pipeline_run_id>/playlist_id=<playlist_id>/
├── artifacts/
└── metadata/
    ├── curation/<pipeline_run_id>/complete.json
    └── pipeline_runs/
```

Bronze is source-shaped and immutable. Silver is typed Snappy Parquet. Metadata records physical curation and run evidence separately from analytical rows.

Terraform declares versioning, SSE-S3 encryption, public-access blocking and TLS-only access for the intended reusable environment.

---

## 9. Spark / Glue Contract

AWS Glue 5.1 runs Apache Spark 3.5.6 / Python 3.11.

Technical responsibilities:

- explicit `StructType` schemas;
- source-item type validation;
- extraction/normalization of tracks, artists and albums;
- many-to-many track/artist expansion;
- deterministic deduplication;
- playlist slot preservation;
- rejected-item accounting;
- Parquet serialization;
- completion manifest publication.

The six curated datasets are:

```text
artists
albums
tracks
track_artists
playlist_snapshots
playlist_observations
```

The validated Glue job uses `MaxRetries=0`. External physical work is retried through explicit orchestration semantics rather than hidden service retries.

---

## 10. Snowflake and Snowpipe Contract

Snowpipe ingests S3 Silver into six typed Landing tables and preserves `METADATA$FILENAME` and `METADATA$FILE_ROW_NUMBER` for reconciliation.

Snowpipe file tracking is not treated as application-level business deduplication. Physical completeness is proved by the Airflow Landing gate; logical idempotency is enforced by dbt model grain and merge semantics.

The database is organized as:

```text
SPOTIFY_ANALYTICS
├── LANDING
├── STAGING
├── CORE
└── MARTS
```

---

## 11. dbt Contract

dbt Core 1.12 / `dbt-snowflake` owns:

- staging normalization;
- dimensions and track/artist bridge;
- canonical `fact_playlist_snapshot`;
- incremental merge behavior;
- analytical marts;
- `BI_*` serving views;
- uniqueness, relationship, accepted-value and singular SQL tests.

The live-validated bounded build passed **152/152** nodes/tests, including the replay validation.

---

## 12. Serving Contract

The v1.0.0 public consumption surface is:

```text
BI_PLAYLIST_DAILY
BI_TRACK_DAILY
BI_TRACK_CHANGES
BI_ARTIST_DAILY
```

These views normalize presentation semantics such as one-based positions, duration units, ratios, null behavior and provenance while remaining independent of any dashboard product.

See [`SERVING_CONTRACT.md`](SERVING_CONTRACT.md).

---

## 13. Orchestration Contract

Airflow 3.2.2 runs locally through Docker Compose and uses the Task SDK.

The current DAG is manual by design:

```text
schedule=None
max_active_runs=1
```

Safe tasks inherit bounded exponential retries. Glue submission has `retries=0`, because an ambiguous external `StartJobRun` response cannot be safely repeated blindly.

Glue and Landing waits use reschedule sensors. A two-hour Airflow 3 Deadline Alert and structured failure callbacks provide execution-level failure evidence.

See [`../airflow/README.md`](../airflow/README.md).

---

## 14. Quality Architecture

The platform uses layered fail-closed gates:

```text
source/Bronze contract
    ↓
Spark/Silver technical validation
    ↓
Glue completion inventory
    ↓
exact Landing reconciliation
    ↓
dbt model tests
    ↓
serving coverage contracts
```

See [`DATA_QUALITY.md`](DATA_QUALITY.md).

---

## 15. Observability Architecture

The platform favors a small, inspectable evidence chain rather than claiming a monitoring dashboard that does not exist.

Per-run artifacts include plan, Glue evidence, Landing evidence, dbt results and final run summary. `scripts/generate_run_report.py` consolidates those artifacts into a schema-validated run report that can optionally be published immutably to S3.

See [`OBSERVABILITY.md`](OBSERVABILITY.md).

---

## 16. Replay and Recovery

New reprocessing creates a new DAG run and fresh physical IDs. It does not require deleting historical Bronze/Silver attempts.

The recovery CLI is dry-run by default:

```bash
.venv/bin/python scripts/replay_partition.py --date YYYY-MM-DD --dry-run
```

Operators must not blindly clear/retry the Glue submit task. See [`RUNBOOK.md`](RUNBOOK.md).

---

## 17. Infrastructure as Code

`infra/terraform/` declares:

- S3;
- IAM;
- Lambda;
- Glue;
- CloudWatch log groups;
- AWS Budget notifications.

CI validates Terraform formatting, initialization without backend, syntax, TFLint and Checkov without AWS credentials.

The release does **not** claim that the pre-existing validated live resources are already owned by Terraform state. No apply/destroy cycle was performed merely to manufacture that claim.

---

## 18. Security Model

Core security principles:

- no committed credentials;
- local secrets remain in ignored paths;
- OAuth access tokens are short lived;
- source credentials are represented in cloud configuration by a secret ARN, not committed values;
- IAM permissions are scoped to workload responsibilities;
- Snowflake transformation and analyst roles are separated;
- CI does not need cloud credentials for static/platform contracts.

See [`SECURITY.md`](SECURITY.md).

---

## 19. Cost Model

The reusable portfolio budget target is **USD 20/month**. This is an operating target and notification threshold, not an automatic cloud-account shutdown.

Structural controls include:

- local Airflow instead of MWAA;
- no always-on EC2/EMR/Kubernetes;
- no required NAT Gateway in the Terraform Lambda design;
- bounded Glue workers/concurrency/timeout;
- Snowflake X-Small with 60-second auto-suspend and resource monitor;
- seven-day CloudWatch retention;
- Terraform AWS Budget actual/forecast notifications at 50% and 90%.

The live validation used an additional manual USD 5 AWS Budget guardrail. Measured usage evidence includes **589 DPU-seconds** across four successful Glue validation runs and **0.45 cumulative Snowflake credits** after the final bounded validation/replay; neither figure should be misrepresented as isolated per-run dollar cost.

See [`COST_STRATEGY.md`](COST_STRATEGY.md).

---

## 20. CI / Validation Matrix

GitHub Actions validates six independent concerns:

```text
Terraform checks
Lint & Test (Python 3.12)
Spark Contracts (Glue 5.1 parity)
Snowflake SQL Contracts
dbt Parse Contracts
Airflow DAG and service contracts
```

The v1.0.0 release was cut from a green `main` build.

---

## 21. Validated Release Evidence

The bounded portfolio slice demonstrated:

- three snapshot dates processed end to end;
- exactly three Glue submissions for that bounded run;
- all Glue runs successful;
- exact Landing gates for all six datasets;
- dbt **152/152** passing nodes/tests;
- four `BI_*` serving views queried with `SPOTIFY_ANALYST`;
- a one-day replay with a second **152/152** dbt build;
- replayed date remaining **12 rows / 12 unique fact grains**;
- total fact count remaining **36**.

The demo's temporal evolution is synthetic and must remain labeled as such.

---

## 22. Documentation Map

| Document | Primary purpose |
|---|---|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Detailed topology, boundaries and trade-offs. |
| [`LOCAL_INGESTION.md`](LOCAL_INGESTION.md) | Spotify source/auth and Bronze contracts. |
| [`DATA_MODEL.md`](DATA_MODEL.md) | Warehouse grains, schemas and analytical semantics. |
| [`DATA_QUALITY.md`](DATA_QUALITY.md) | Cross-tier fail-closed quality gates. |
| [`SERVING_CONTRACT.md`](SERVING_CONTRACT.md) | BI-tool-agnostic serving views and units. |
| [`OBSERVABILITY.md`](OBSERVABILITY.md) | Run evidence and unified telemetry. |
| [`RUNBOOK.md`](RUNBOOK.md) | Incident triage and safe recovery. |
| [`SECURITY.md`](SECURITY.md) | Credentials, IAM and RBAC boundaries. |
| [`COST_STRATEGY.md`](COST_STRATEGY.md) | Cost controls and measured usage evidence. |
| [`DEMO_GUIDE.md`](DEMO_GUIDE.md) | Portfolio presentation sequence. |
| [`INTERVIEW_GUIDE.md`](INTERVIEW_GUIDE.md) | Technical discussion and trade-offs. |
| [`REFERENCES.md`](REFERENCES.md) | Primary technical references and source attribution. |

---

## 23. Extension Points Beyond v1.0.0

Reasonable future experiments include:

- managed production-grade orchestration only if an operating need justifies it;
- OIDC-based deployment automation;
- open table formats such as Apache Iceberg when lake mutation/time-travel semantics justify the complexity;
- managed metrics/traces and pager integration for production SLOs;
- a BI dashboard as a separate analytics-consumer project;
- additional data-quality tooling only if it adds capabilities beyond the existing contract suite.

These are extension points, not missing prerequisites for the current data-engineering portfolio release.
