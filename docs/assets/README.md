# Documentation Visual Production Brief

This directory contains the visual-production contract for the Spotify Analytics Data Platform documentation.

The diagrams should behave like **technical documentation**, not decorative marketing art. Every visual must reduce cognitive load, preserve the repository's evidence boundary, and remain readable on GitHub at desktop width.

## Global visual standard

- Premium corporate technical-diagram aesthetic.
- Light or white background with modern sans-serif typography.
- Clean horizontal composition, preferably 16:9.
- Subtle domain grouping with rounded borders and restrained shadows.
- Use semantic colors consistently across diagrams.
- Keep text short and use crisp arrows with one unambiguous direction of flow.
- Avoid photorealism, 3D scenes, people, fake UI screenshots and generic stock-art styling.
- Export at least 2400 px wide as PNG and keep a lossless/source version when possible.
- The first three approved diagrams are original 1672 × 941 PNG exports, included without recompression. Target at least 2400 px for future generations; this is not a claim about the existing images.
- Do not show Power BI as implemented in v1.0.0.
- Do not depict the Spotify API/Lambda route as the live-validated public-demo path.
- Do not imply Terraform applied or destroyed the existing validated cloud environment.

Status semantics: **Validated** = green; **Implemented / contract-validated** = blue; **Optional / target path** = dashed neutral/blue; **Deferred** = muted gray.

## Integrated visual assets

| Asset | Primary placement | Reuse | Status |
|---|---|---|---|
| [`architecture-overview.png`](readme/architecture-overview.png) | `README.md` → Architecture at a Glance | `docs/ARCHITECTURE.md` → Architecture in One View | Original PNG integrated |
| [`validated-demo-path.png`](readme/validated-demo-path.png) | `README.md` → Validated Evidence | — | Original PNG integrated |
| [`implemented-deferred-extensions.png`](architecture/implemented-deferred-extensions.png) | `docs/ARCHITECTURE.md` → Scope Boundaries and Deferred Components | Optional future demo guide | Original PNG integrated |

Other briefs below remain prompts/placeholders; they do not imply the corresponding image or a live dashboard exists.

---

## 01 — Architecture overview

**Save as:** `docs/assets/readme/architecture-overview.png`

**README placement:** `Architecture at a Glance`

### Prompt

Create a premium, executive-grade technical architecture diagram titled **“Spotify Analytics Data Platform — End-to-End Architecture”**.

The image is for the main README of a senior data engineering portfolio. Use a clean white background, sharp typography, balanced whitespace, restrained colors, clear arrows, subtle rounded domain boxes and a wide 16:9 layout.

Represent these domains from left to right: Sources; Ingestion & Raw Storage; Technical Transformation; Warehouse Ingestion; Analytics Engineering; Serving; Orchestration; Platform Controls.

The primary solid flow must read: **CC0 snapshots → S3 Bronze → Glue/Spark → S3 Silver → Snowpipe → Snowflake LANDING → dbt → Snowflake MARTS / BI views**.

The optional source branch must read **Spotify Web API → AWS Lambda → S3 Bronze** and be clearly labeled **“Optional live-source path — not part of the validated public demo”**.

Show Airflow 3.2.2 in Docker coordinating the stages with Task SDK, readiness gates, Deadline Alert and run evidence. Show Terraform, GitHub Actions, data-quality gates, unified telemetry and replay/recovery tooling as cross-cutting controls.

Do not show Power BI as implemented. Do not include Kafka, Kubernetes, Redshift, Databricks or MWAA. Do not imply Terraform apply/destroy was executed for the validated environment.

The result should be understandable to both a recruiter and a senior data engineer within 15 seconds.

---

## 02 — Validated demo path vs optional extensions

**Save as:** `docs/assets/readme/validated-demo-path.png`

**README placement:** `Validated Evidence`

### Prompt

Create a premium comparison diagram titled **“Validated v1.0.0 Path vs Optional Extensions”** with a clean white background and two clearly separated zones.

In the **LIVE-VALIDATED BOUNDED PATH** zone, show a solid flow through CC0-backed snapshots → Amazon S3 Bronze → AWS Glue 5.1 / Spark 3.5.6 → S3 Silver / Parquet → Snowpipe → Snowflake LANDING → dbt Core 1.12 → Snowflake CORE / MARTS → BI-serving views, with Apache Airflow 3.2.2 / Docker coordinating the run. Also show cross-tier quality gates, unified run evidence and safe one-day replay.

Add a compact evidence panel: **3 snapshot dates processed end to end; 152/152 dbt nodes/tests passed; replay retained 12 rows / 12 unique fact grains on the replayed date; 36 total fact rows after replay**.

In the **IMPLEMENTED / DEFERRED EXTENSIONS** zone, show: Spotify Web API → AWS Lambda as “implemented/tested source contract; not part of validated public demo”; Terraform live-state ownership as “IaC validated offline; no apply/destroy claim for v1.0.0”; and Power BI semantic model / DAX / dashboard as “deferred from v1.0.0”.

Use concise status icons and a legend for **live validated**, **implemented / contract validated**, and **deferred**. The visual should communicate technical honesty and intentional scope, not unfinished work.

---

## 03 — Data layers flow

**Save as:** `docs/assets/readme/data-layers-flow.png`

**README placement:** `End-to-End Data Flow`

### Prompt

Create a premium technical data-layer diagram titled **“Data Flow Across Platform Layers”** using six elegant horizontal stages connected left to right.

Show **Source / Bronze** with raw JSON snapshots, immutable physical run paths and lineage fields `pipeline_run_id`, `spotify_snapshot_id`, `snapshot_date`; **Silver** with AWS Glue 5.1 / Spark 3.5.6, typed Snappy Parquet, six curated datasets and a completion manifest; **Landing** with Snowpipe → Snowflake LANDING plus file/row audit metadata; **Staging** with dbt normalization views; **Core / Marts** with Kimball dimensions, bridge, canonical fact, incremental merge and analytical marts; and **Serving** with the four `BI_*` views.

Under the stages, add a thin quality rail: **Bronze validation → Silver technical contracts → exact Landing readiness → dbt integrity tests → serving coverage tests**.

Near Core, call out the canonical business grain **(playlist_id, snapshot_date, track_position)** and explicitly note that `pipeline_run_id` is physical lineage, not part of the analytical primary grain.

Do not show Power BI. Keep the visual minimal, architectural and easy to scan.

---

## 04 — Airflow orchestration model

**Save as:** `docs/assets/readme/orchestration-dag.png`

**README placement:** `Engineering Highlights → Orchestration built for safe external execution`

### Prompt

Create a premium workflow diagram titled **“Airflow 3 Orchestration Model — spotify_daily_snapshot”** that reflects the actual repository rather than a generic Airflow DAG.

Use the left-to-right flow **prepare → records → [upload → submit Glue → await Glue → await Landing] per snapshot → transform / dbt build → report** and show that the bracketed chain can exist once per requested snapshot date.

Add compact reliability callouts: Airflow 3.2.2 Task SDK; `schedule=None` for explicit bounded manual execution; `max_active_runs=1`; fresh UUID v4 `pipeline_run_id`; safe tasks use 3 retries, five-minute initial delay and exponential backoff; Glue submit uses `retries=0`; waiting tasks avoid tight polling; two-hour Deadline Alert; structured `DAG_FAILED` and `DAG_DEADLINE_MISSED` callbacks; final report/evidence task uses all-done semantics without masking upstream failure.

Visually emphasize **“Glue submit is deliberately not blindly retried”** with the annotation “ambiguous external submit could duplicate physical work”. Use S3, Glue, Snowflake, dbt and JSON/document icons only where they improve clarity. Airflow must appear as coordinator, not as compute engine.

---

## 05 — Data quality and observability controls

**Save as:** `docs/assets/readme/quality-observability.png`

**README placement:** `Engineering Highlights → Cross-tier quality gates / Evidence-first observability`

### Prompt

Create a premium technical diagram titled **“Data Quality and Observability Controls”** with two synchronized lanes across the same pipeline stages.

In the upper **DATA QUALITY GATES** lane, show Bronze payload/lineage validation; Silver explicit schemas, valid item types and rejected-item accounting; Landing exact run-scoped filenames, expected row counts, distinct file-row numbers and no unexpected files; dbt/Core uniqueness, relationships, accepted values and canonical grain integrity; and Serving row-key/coverage contracts. Use a fail-closed stop symbol between stages to show that downstream work is blocked when a gate fails.

In the lower **RUN EVIDENCE / OBSERVABILITY** lane, show `plan.json`, `glue-<pipeline_run_id>.json`, the Glue completion manifest in S3, `landing-<pipeline_run_id>.json`, `dbt-summary.json`, `run-summary.json`, and the consolidated `pipeline-run-report.json`.

The consolidated report should visibly carry Airflow run ID, pipeline run ID, source/snapshot identity, status, extracted/curated/loaded counts, Glue execution metadata, dbt node count and elapsed time, and component durations. Add an optional arrow to `S3 metadata/pipeline_runs/` labeled **“explicit immutable publication”**.

Do not create a fake Grafana or CloudWatch dashboard. The core message is **evidence chain, not dashboard claim**.

---

## 06 — Analytics serving layer

**Save as:** `docs/assets/readme/serving-layer.png`

**README placement:** `Serving Layer`

### Prompt

Create a premium data-consumption diagram titled **“Analytics Serving Layer”** with the flow **Snowflake LANDING → dbt STAGING → CORE star schema → MARTS → BI-serving views → Analyst / BI consumer**.

Inside the serving group, list `BI_PLAYLIST_DAILY`, `BI_TRACK_DAILY`, `BI_TRACK_CHANGES`, and `BI_ARTIST_DAILY`.

Add a compact semantic-contract panel showing: documented grain; one-based display positions; ratios use 0–1 semantics; explicit null handling; source provenance retained; refresh only after successful run summary.

Use a generic **Analyst / BI Tool** icon at the end. Do not use a Power BI logo or imply a dashboard exists. Add a muted note: **“Power BI deferred from v1.0.0; serving contract is tool-agnostic.”**

The diagram should communicate that analytical semantics live in version-controlled dbt/Snowflake models rather than inside a dashboard.

---

## 07 — Infrastructure as Code, CI and cost controls

**Save as:** `docs/assets/readme/iac-ci-cost-controls.png`

**README placement:** `Infrastructure, CI and Cost Controls`

### Prompt

Create a premium platform-engineering diagram titled **“Infrastructure as Code, CI and Cost Controls”** organized into three balanced columns or bands.

In **INFRASTRUCTURE AS CODE**, show Terraform modules for S3, IAM, Lambda, Glue, monitoring and AWS Budget. Label the resource shape with private/public-access-blocked S3, SSE-S3 encryption, least-privilege roles, bounded Glue workers/concurrency/timeout, seven-day log retention and a USD 20 monthly budget contract. Add the status note: **“Defined in Terraform; validated offline. Existing live demo resources were not replaced by apply/destroy for v1.0.0.”**

In **CI VALIDATION**, show GitHub Actions feeding six green tracks: Terraform checks; Lint & Test — Python 3.12; Spark Contracts — Glue 5.1 parity; Snowflake SQL Contracts; dbt Parse Contracts; Airflow DAG & service contracts. Under Terraform checks show `fmt → init -backend=false → validate → TFLint → Checkov` and label **“No cloud credentials required”**.

In **COST GUARDRAILS**, show local Docker Airflow avoiding MWAA baseline cost; no NAT Gateway requirement; bounded/on-demand Glue; Snowflake X-Small with 60-second auto-suspend and a resource monitor; the manual USD 5 budget that protected the validated demo account; and the reusable Terraform AWS Budget defaulting to USD 20 with actual + forecast alerts at 50% and 90%.

Add a small measured-evidence panel: **Glue — 589 total DPU-seconds across four successful validation runs; Snowflake resource monitor — 0.45 cumulative credits after final bounded validation/replay.** Label these explicitly as **usage evidence, not isolated per-run dollar cost**.

---

## Future visual briefs

The deeper documentation sweep adds dedicated prompts as each corresponding document is rewritten.

---

## 08 — Detailed system architecture

**Save as:** `docs/assets/architecture/system-architecture-detailed.png`

**Placement:** `docs/ARCHITECTURE.md → Architecture in One View`

### Prompt

Create a detailed premium system architecture diagram titled **“Spotify Analytics Data Platform — Detailed System Architecture”**. Use a wide 16:9 canvas, white background, restrained enterprise colors, crisp typography and clear grouped domains.

Show the **validated bounded path** as the dominant solid flow: CC0-backed local snapshots → Airflow upload → Amazon S3 Bronze → AWS Glue 5.1 / Spark 3.5.6 → Amazon S3 Silver / Parquet → Snowpipe → Snowflake LANDING → dbt STAGING → CORE → MARTS → four Snowflake BI-serving views.

Show Apache Airflow 3.2.2 / Docker spanning the validated stages as coordinator only, with small labels for physical UUID planning, exact Landing readiness, Deadline Alert, structured failure callbacks, run evidence and safe replay.

Show a clearly separate dashed **optional live-source path**: Spotify Web API → AWS Lambda / Python 3.12 → S3 Bronze, supported by OAuth Authorization Code + refresh token and AWS Secrets Manager. Label it **“implemented/contract-tested source path — not part of validated public demo”**.

Add cross-cutting platform controls: Terraform; GitHub Actions; least-privilege IAM; cost guardrails; unified run telemetry. Make it visually clear that Terraform is validated offline and does not imply state ownership of the already existing live demo resources.

Do not show Power BI as implemented. Do not show Airflow processing data itself. The diagram should support a senior-level architecture review with more depth than the README overview while remaining readable.

---

## 09 — Component responsibilities

**Save as:** `docs/assets/architecture/component-responsibilities.png`

**Placement:** `docs/ARCHITECTURE.md → Component Responsibilities`

### Prompt

Create a premium architecture responsibility map titled **“Component Responsibilities and Boundaries”** using a clean card/grid layout.

Include cards for: CC0 demo adapter; Spotify Web API client; AWS Lambda; S3 Bronze; AWS Glue 5.1 / Spark; S3 Silver; Snowpipe; Snowflake LANDING; dbt Core; Apache Airflow 3.2.2; Terraform; GitHub Actions; Snowflake BI views.

Each card should contain exactly three concise rows: **Owns**, **Does not own**, and **Evidence status**.

Use these core boundaries: Airflow owns coordination but not heavy processing; Glue/Spark owns technical source-shape curation but not business semantics; dbt/Snowflake owns analytical semantics but not raw API normalization; S3 Bronze owns immutable physical input evidence; Snowflake Landing owns typed ingestion plus file audit metadata; BI views own tool-agnostic serving semantics; Terraform owns desired AWS resource definition but does not by itself prove live state ownership.

Use status accents for live validated, implemented/contract-tested and offline validated. The visual should immediately communicate separation of concerns.

---

### Prompts still to be added during the sweep

All currently referenced documentation visuals now have dedicated generation briefs below.

---

## 10 — Detailed Airflow DAG flow

**Save as:** `docs/assets/airflow/spotify-daily-snapshot-dag-flow.png`

**Placement:** `airflow/README.md → DAG Execution Model`

### Prompt

Create a premium workflow diagram titled **“spotify_daily_snapshot — Airflow 3 Task Flow”**. Use a horizontal DAG layout with a white background, Airflow-style task cards and restrained service colors.

Show `prepare → records`, then dynamic mapped curation lanes for multiple snapshot dates. Each mapped lane must show **upload → submit Glue → await Glue → await Landing**. Merge all mapped lanes into **transform / dbt build**, then **report** as the only leaf task.

For `prepare`, show “validate config + bounded date window + generate physical UUID plan”. For `upload`, show immutable S3 Bronze. For `submit`, show AWS Glue. For `await Glue`, show reschedule sensor / 60-minute timeout. For `await Landing`, show exact Snowflake readiness / 15-minute timeout. For `transform`, show dbt build in Snowflake. For `report`, show final run summary/evidence.

Use small badges to show `schedule=None`, `max_active_runs=1`, and Task SDK. Clearly annotate that each mapped snapshot gets its own UUID v4 `pipeline_run_id` and immutable evidence path.

Do not include Lambda in this validated DAG flow. Do not present Airflow as the transformation engine.

---

## 11 — Airflow reliability controls

**Save as:** `docs/assets/airflow/reliability-controls.png`

**Placement:** `airflow/README.md → Reliability Controls`

### Prompt

Create a premium reliability-control diagram titled **“Airflow Reliability Controls”**. Organize it around four concepts: **Safe Retry**, **External Submit Safety**, **Readiness / Sensors**, and **Deadline & Failure Evidence**.

Under Safe Retry show: 3 retries, five-minute initial delay, exponential backoff for safe tasks, and immutable upload retry only when bytes are identical.

Under External Submit Safety show `curate.submit`, `retries=0`, SDK `StartJobRun` retries disabled, immutable submission claim, and the warning **“Do not blindly clear/retry Glue submission — ambiguous response can duplicate physical work.”**

Under Readiness / Sensors show Glue sensor in reschedule mode, Landing sensor in reschedule mode, exact file/row readiness before dbt, and no tight worker polling.

Under Deadline & Failure Evidence show a two-hour Airflow 3 `DeadlineAlert` referenced to `DAGRUN_QUEUED_AT`, structured `DAG_FAILED` and `DAG_DEADLINE_MISSED` events, and `report` with `all_done` semantics that still raises when upstream work is incomplete.

Use arrows or a control-ring design to show that these controls surround the DAG rather than forming another data-processing layer.

---

## 12 — Terraform scope and validation boundary

**Save as:** `docs/assets/terraform/terraform-scope-validation.png`

**Placement:** `infra/terraform/README.md → opening ownership boundary`

### Prompt

Create a premium staff-level infrastructure diagram titled **“Terraform Desired State — Scope, Validation and Live Ownership Boundary”** for a senior data-engineering portfolio. Use a wide 16:9 canvas, off-white background, crisp sans-serif typography, generous whitespace, subtle rounded containers, orthogonal connectors and restrained AWS/Terraform colors. The result must look like formal platform-engineering documentation rather than marketing art.

Organize the diagram into three horizontal zones:

1. **TERRAFORM DESIRED STATE — IMPLEMENTED**. Show the root module composing five bounded areas: **S3 lake**, **IAM**, **Lambda**, **Glue**, and **Monitoring / AWS Budget**. Inside the S3 lake show one private versioned bucket with `bronze/`, `silver/`, `artifacts/`, and `metadata/`; SSE-S3 AES-256; all public access blocked; `BucketOwnerEnforced`; non-TLS denied; seven-day multipart cleanup; 30-day non-current version expiration. Show Lambda as Python 3.12, reserved concurrency 1, 30-second timeout. Show Glue 5.1 as FLEX, 2 × G.1X, max concurrent runs 1, 15-minute timeout. Show CloudWatch log groups with seven-day retention. Show the reusable AWS Budget default as **USD 20/month with actual + forecast alerts at 50% and 90%**.
2. **LEAST-PRIVILEGE TRUST GRAPH**. Show three separate roles with no shared broad allow policy: Lambda → `PutObject` only to `bronze/spotify/*`, `GetSecretValue` only for one configured secret ARN, log stream/event writes only to its own log group; Glue → read Bronze + Glue artifacts, manage Silver outputs, read/write completion metadata, log writes only to Glue groups; Snowflake storage role → trust only the configured Snowflake-generated IAM user plus `sts:ExternalId`, read-only list/get access to `silver/*`. Add a note that `s3:*` exists only in a **Deny insecure transport** bucket-policy statement, never as a workload allow grant.
3. **VALIDATION / OWNERSHIP BOUNDARY**. Show GitHub Actions running `terraform fmt → init -backend=false → validate → TFLint → Checkov` with a clear badge **“offline / no cloud credentials”**. Then place a bold vertical boundary before a separate muted box labeled **“Validated v1.0.0 live demo environment”**. Connect Terraform to that box with **no ownership arrow**. Instead add the caption: **“No Terraform apply, import or destroy was executed against the validated demo environment; live state ownership is not claimed.”**

Add compact tags: `Project = SpotifyAnalyticsDataPlatform`, `Environment = dev`, `ManagedBy = Terraform`. Add a small footer note: **“Desired state is production-quality and reusable; live ownership begins only after explicit state-backed creation/import and reconciliation.”**

Do not imply that Terraform created the v1.0.0 live S3/Glue/Snowflake demo resources. Do not show a successful `apply` or `destroy` icon. Do not introduce VPC, NAT Gateway, EC2, EMR, RDS, Redshift or Kubernetes. Keep the emphasis on reproducible desired state, least privilege and honest evidence boundaries.

---

## 13 — Cost governance and evidence

**Save as:** `docs/assets/cost/cost-governance-evidence.png`

**Placement:** `docs/COST_STRATEGY.md → opening cost-control model`

### Prompt

Create an executive-grade technical cost-governance diagram titled **“Cost Governance — Guardrails, Usage Evidence and Ownership Boundaries”**. Use a wide 16:9 layout with an off-white background, restrained enterprise colors, compact typography, clean metric cards and no decorative finance imagery. The visual must communicate engineering controls and evidence provenance, not a generic cloud-cost dashboard.

Build three aligned bands:

**ARCHITECTURAL GUARDRAILS** — show Local Docker Airflow instead of MWAA; no NAT Gateway; no always-on EC2/EMR; AWS Lambda only for the optional source path with reserved concurrency 1; AWS Glue 5.1 on demand using FLEX, 2 × G.1X, one concurrent run and a 15-minute timeout; one private S3 lake with bounded version retention; CloudWatch logs retained seven days; Snowflake `COMPUTE_WH` as single-cluster X-Small with `AUTO_SUSPEND = 60`, `AUTO_RESUME = TRUE`, initially suspended, 120-second queued timeout and 900-second statement timeout.

**FINANCIAL / QUOTA CONTROLS** — show two clearly separate AWS Budget cards. Card A: **“Live v1.0.0 demo — manual AWS Budget: USD 5/month”** with status **live guardrail used during bounded validation**. Card B: **“Reusable Terraform contract — USD 20/month default”** with four alert chips: **50% actual**, **50% forecast**, **90% actual**, **90% forecast**. Label Card B **implemented + validated offline/CI; not applied to the validated demo environment**. Beside Snowflake show `SPOTIFY_DEV_MONITOR`, **2 credits/month**, **notify at 80%**, **SUSPEND_IMMEDIATE at 100%**. Add a small note: **“AWS Budget alerts notify; they do not hard-stop the AWS account. Snowflake resource monitor constrains warehouse compute, not Snowpipe serverless usage.”**

**MEASURED USAGE EVIDENCE** — show two evidence cards with strong provenance labels. Card 1: **AWS Glue — 589 DPU-seconds**, scope **four successful Airflow-orchestrated validation runs: bounded three-day slice + one-day replay**. Card 2: **Snowflake — 0.45 cumulative credits**, scope **resource-monitor reading after final bounded validation/replay**. Between the cards and any currency symbol, place a visible prohibition marker and the caption **“Usage evidence ≠ isolated per-run dollar cost.”** Explain in one concise line that Glue price depends on region/billing rules and Snowflake credit price depends on account/cloud/region, while `0.45` is cumulative since monitor creation.

Use a small legend: **Live control**, **Reusable contract**, **Measured usage**, **Not claimed**. Do not calculate a dollar cost from 589 DPU-seconds or 0.45 credits. Do not imply the Terraform USD 20 budget replaced the manual USD 5 demo budget. Do not show the v1.0.0 live environment as Terraform-owned.

---

## 14 — Security trust boundaries and least privilege

**Save as:** `docs/assets/security/security-trust-boundaries.png`

**Placement:** `docs/SECURITY.md → Security Posture at a Glance`

### Prompt

Create a premium security architecture diagram titled **“Security Trust Boundaries and Least-Privilege Access”** for the Spotify Analytics Data Platform v1.0.0. Use a 16:9 off-white canvas, orthogonal connectors, subtle trust-boundary containers, restrained AWS/Snowflake colors, crisp typography and a formal security-review aesthetic. Avoid lock/shield clip-art unless used sparingly as a small semantic icon.

Show four trust zones from left to right and top to bottom:

1. **SOURCE / CREDENTIAL ZONE** — Spotify operator authorization produces `client_id`, `client_secret`, `refresh_token`. In cloud mode those values live in **AWS Secrets Manager**. Draw the Lambda environment containing only the **secret ARN**, never the credential values. Show local development as a separate small branch: `ENVIRONMENT=local → process environment`, with the guard **“rejected inside managed Lambda runtime”**. Add **“no secret write permission in v1.0.0”** and **“invalid_grant clears warm credential cache”**.
2. **AWS DATA PLANE** — one private S3 bucket with `bronze/`, `silver/`, `artifacts/`, `metadata/`, public access blocked, `BucketOwnerEnforced`, SSE-S3 AES-256, versioning, and bucket-policy deny for non-TLS traffic. Show Lambda role permissions exactly: `s3:PutObject → bronze/spotify/*`; `secretsmanager:GetSecretValue → exact secret ARN`; `logs:CreateLogStream + PutLogEvents → own log group`. Show Glue permissions as: list constrained required prefixes; read Bronze + Glue artifacts; get/put/delete/abort multipart only for Silver; get/put metadata; log writes only to Glue log groups. Explicitly show **no wildcard allow actions for these sensitive workload permissions**.
3. **CROSS-ACCOUNT SNOWFLAKE TRUST** — show the Snowflake storage integration assuming one AWS role only when both **Snowflake-generated IAM user ARN** and **`sts:ExternalId`** match. From that role to S3 draw a one-way read arrow restricted to `silver/*` with `ListBucket` prefix constraint plus `GetObject` / `GetObjectVersion`. Add **“no static AWS access keys; no S3 write/delete permission for Snowflake”**.
4. **SNOWFLAKE RBAC** — show three separate role cards: `SPOTIFY_LOADER` = LANDING + pipe duties, **no warehouse usage required for serverless Snowpipe**; `SPOTIFY_TRANSFORMER` = `COMPUTE_WH` usage, read LANDING, create tables/views in STAGING/CORE/MARTS; `SPOTIFY_ANALYST` = `COMPUTE_WH` usage and read-only MARTS. Keep `ACCOUNTADMIN` / `SYSADMIN` outside the runtime zone, labeled **controlled administration only**.

Across the bottom, add a thin **VALIDATION / LIMITATIONS** rail: Terraform `fmt/init-backend=false/validate/TFLint/Checkov`; Snowflake SQL contracts; no cloud credentials in CI; explicit Checkov skips for bounded dev tradeoffs such as no Lambda VPC/NAT, no customer-managed KMS, seven-day logs, no X-Ray/DLQ/code signing. End with a distinct muted box: **“v1.0.0 live demo resources were manually controlled; no Terraform apply/import/destroy ownership claim.”**

Do not depict the repository as compliance-certified. Do not imply customer-managed KMS, private networking, long-term audit retention or automated secret rotation/write-back exists. Do not use `logs:CreateLogGroup` in the Lambda/Glue runtime permissions because Terraform pre-creates the log groups. Do not show broad S3 wildcard allow policies; if `s3:*` appears, label it clearly as **Deny insecure transport only**.


---

## 15 — Unified run telemetry and immutable evidence

**Save as:** `docs/assets/observability/unified-run-telemetry.png`

**Placement:** `docs/OBSERVABILITY.md → Evidence Architecture`

### Prompt

Create a premium staff-level observability architecture diagram titled **“Unified Pipeline Telemetry — Evidence Chain, Correlation and Validation Boundaries”** for the Spotify Analytics Data Platform v1.0.0. Use a wide 16:9 canvas, off-white or white background, crisp sans-serif typography, orthogonal connectors, generous whitespace, thin rounded containers and restrained enterprise colors. The visual must look like formal engineering documentation, not a monitoring-dashboard mockup.

Split the composition into two clearly separated source surfaces that converge only at the S3 Bronze boundary:

1. **BOUNDED CC0 DEMO — VALIDATED PUBLIC PATH**. Make this the dominant solid lane. Start with **CC0-backed generated Bronze snapshots** labeled `source_type=cc0_demo` and `temporal_state=synthetic`. Continue through **Airflow 3.2.2 plan → immutable S3 Bronze → AWS Glue 5.1 / Spark 3.5.6 → Glue completion manifest → S3 Silver → Snowpipe → Snowflake LANDING exact gate → dbt build → run-summary.json → pipeline-run-report.json**. Do not place Lambda or Spotify Web API in this solid lane.
2. **SPOTIFY LIVE SOURCE — IMPLEMENTED / CONTRACT-TESTED**. Show a separate dashed blue branch **Spotify Web API → AWS Lambda / Python 3.12 → structured lifecycle events + immutable S3 Bronze**. Label it prominently **“Implemented and contract-tested source path — not exercised by the bounded public demo”**. Show event chips `EXTRACTION_START`, `PAGINATION_PAGE_FETCHED`, `S3_WRITE_SUCCESS`, `EXTRACTION_COMPLETE`, `EXTRACTION_FAILED`. Make `EXTRACTION_FAILED` carry **exception type only / no exception body**.

In the center, add a **CORRELATION MODEL** rail with five aligned identity cards: `airflow_run_id` = orchestration attempt; `run_key` = SHA-256-derived storage-safe key; `pipeline_run_id` = physical playlist/date publication; `spotify_snapshot_id` = source version, live or explicitly simulated; `snapshot_date` = logical business observation date. Add the invariant **“Replay keeps logical identity; new DAG run gets fresh physical identity.”**

Under the bounded batch lane, render the evidence artifacts in sequence: `plan.json`; `metadata/curation/<pipeline_run_id>/submission.json`; `glue-<pipeline_run_id>.json`; `metadata/curation/<pipeline_run_id>/complete.json`; `landing-<pipeline_run_id>.json`; `dbt-summary.json`; `run-summary.json`; `pipeline-run-report.json`. Mark the S3 submission claim and optional final S3 report publication with **immutable conditional write — IfNoneMatch="*"**. Mark local JSON evidence as run-scoped artifacts, not source payloads.

Make the **EXACT LANDING GATE** visually strong. Show six dataset chips: artists, albums, tracks, track_artists, playlist_snapshots, playlist_observations. List the checks compactly: exact run-scoped filenames; expected rows from Glue inventory; distinct `_FILE_ROW_NUMBER`; no unexpected/repeated/excess files; missing positive-row files = not ready; zero rejected demo items. Draw a fail-closed barrier before dbt.

Inside the final `pipeline-run-report.json` card, show the most important schema-v1 fields without overloading the visual: `status`, `source_type`, `temporal_state`, Airflow total duration, Glue total execution time, dbt elapsed time, dbt nodes passed; and inside `physical_runs[]`: `pipeline_run_id`, `spotify_snapshot_id`, `snapshot_date`, `records_extracted`, `glue_job_run_id`, `glue_execution_time_seconds`, `glue_dpu_seconds`, `landing_ready`, `rejected_items`, curated rows by dataset, loaded rows by dataset. Add the note **“For CC0 demo, records_extracted = generated Bronze item count; it is not evidence of live Lambda extraction.”**

Add a top-right **AIRFLOW RELIABILITY EVENTS** panel with **DeadlineAlert — 2h from DAGRUN_QUEUED_AT**, **DAG_FAILED**, and **DAG_DEADLINE_MISSED**. State that callback payloads contain safe run/task identifiers and exception class only. Label these as structured application events, not proof of pager or CloudWatch alarm delivery.

At the bottom, include a small truth-boundary legend: **Validated bounded demo**, **Implemented / contract-tested**, **Immutable evidence**, **Not claimed**. Under Not claimed list **CloudWatch/Grafana dashboard**, **managed alert delivery**, and **Power BI dashboard validation**.

Do not create fake Grafana, Datadog or CloudWatch dashboard panels. Do not merge the Lambda live-source lane into the validated CC0 lane. Do not imply that a CC0 run proves live Spotify extraction. Do not omit the exact Landing gate or the immutable-evidence semantics. The main message should be: **observability is reconstructable evidence, not a dashboard claim**.

---

## 16 — Incident recovery and safe replay flow

**Save as:** `docs/assets/runbook/recovery-flow.png`

**Placement:** `docs/RUNBOOK.md → Recovery Invariants / First Five Minutes`

### Prompt

Create a premium incident-recovery flowchart titled **“Safe Recovery Flow — Diagnose, Preserve Evidence, Replay, Re-Prove”** for the Spotify Analytics Data Platform v1.0.0. Use a wide 16:9 off-white canvas, strict orthogonal routing, restrained service colors, clear decision diamonds, compact evidence cards and generous whitespace. The diagram should read like an SRE/data-platform runbook, not a generic business-process chart.

Start with one entry node: **“Airflow run / source execution failed or exceeded deadline”**. Immediately split into two clearly labeled domains:

- **LIVE SPOTIFY SOURCE PATH — separate recovery surface**: branches for `invalid_grant`, HTTP 429/quota pressure, and `spotify_snapshot_id` drift during pagination. For `invalid_grant`, show **interactive reauthorization → update AWS Secrets Manager securely → invoke live source path again**, with a security note **“never paste token values into CLI args, logs, screenshots or tickets”**. For 429 show **respect Retry-After / avoid immediate quota retry loops**. For snapshot drift show **abort mixed-version attempt → fresh physical source execution**. Label the whole lane **“Implemented/contract-tested source path — not recovered by replay_partition.py”**.
- **BOUNDED CC0 AIRFLOW DEMO — validated recovery path**: this is the main solid lane and is the only lane that uses `scripts/replay_partition.py`.

For the bounded lane, enforce this sequence visually:

**1. IDENTIFY** → record `airflow_run_id`, `run_key`, affected `pipeline_run_id`.

**2. FIND LAST PROVEN BOUNDARY** → inspect, in order, `plan.json`, immutable Bronze object, Glue `submission.json`, `glue-<pipeline_run_id>.json`, Glue `complete.json`, `landing-<pipeline_run_id>.json`, dbt `run_results.json`, `run-summary.json`.

**3. AMBIGUOUS GLUE SUBMIT?** decision diamond. If yes: show **inspect immutable submission claim + AWS Glue job runs** and a bold red prohibition **“DO NOT clear/retry curate.submit while remote state is ambiguous”**. Only after the prior external attempt is failed/stopped/settled may the flow continue to a new DAG run. Annotate that Glue submit has `retries=0` because a client timeout can hide successful remote submission.

**4. LANDING DELAY?** decision diamond. If yes: run **`audit_landing_lag.py --hours 24 --dry-run` first**, then optional read-only COPY_HISTORY audit. Show the exact-gate requirements beside it: six declared datasets, exact run-scoped filenames, expected row counts, distinct `_FILE_ROW_NUMBER`, no unexpected/repeated/excess files, zero rejected demo items. Add **“Do not use ad-hoc COPY INTO as the default recovery path.”**

**5. PREVIEW REPLAY** → **`replay_partition.py --date YYYY-MM-DD --entity playlist_tracks`** with a green badge **“dry-run by default”**. Show checks: one logical date; future dates rejected; bounded CC0 manifest contains date; Airflow environment configured; ambiguous Glue state settled.

**6. EXECUTE CLEAN REPLAY** → **same command + `--execute`**. Add two identity badges: **new Airflow run → fresh `pipeline_run_id` and new physical Bronze/Silver paths**; **logical `snapshot_date` / canonical business grain stays intentional**. Add a no-delete/no-overwrite symbol over prior physical publications.

**7. RE-PROVE** → Glue completion manifest → exact six-dataset Landing gate → dbt build → `run-summary.json status=success` → generate `pipeline-run-report.json` → compare previous vs replay evidence. The success state should require all of these, not just a green Airflow task.

Add a side reliability panel with: **safe tasks: 3 retries + five-minute initial delay + exponential backoff**; **Glue sensor: reschedule / 60-minute timeout**; **Landing sensor: reschedule / 15-minute timeout**; **DAG timeout: 2h**; **DeadlineAlert: 2h from DAGRUN_QUEUED_AT**; structured events **DAG_FAILED** and **DAG_DEADLINE_MISSED** with exception class only. Label Deadline missed as **latency signal, not root-cause diagnosis**.

Use visual status semantics: green = proven/safe to proceed; amber = investigate/ambiguous; red = prohibited unsafe action; blue = implemented operational mechanism; dashed blue = live-source recovery surface outside the bounded demo. Include a footer **“Preserve evidence first. Recovery creates a new physical execution when a new attempt is required.”**

Do not show deletion of old S3 data, manual construction of `pipeline_run_id`, blind Glue resubmission, ad-hoc Snowflake COPY as the preferred fix, or Power BI validation. Do not imply CloudWatch paging exists. The visual must make the safe replay boundary and exact Landing gate unmistakable.

---

## 17 — Warehouse modeling layers

**Save as:** `docs/assets/data-model/modeling-layers.png`

**Placement:** `docs/DATA_MODEL.md → Architectural Modeling Tiers`

### Prompt

Create a premium warehouse-modeling diagram titled **“Warehouse Modeling Layers — Physical Ingestion to Analytical Serving”** for the Spotify Analytics Data Platform v1.0.0. Use a clean 16:9 white/off-white canvas, modern sans-serif typography, restrained Snowflake/dbt colors, horizontal flow, generous whitespace and subtle rounded containers.

Show five connected layers: **LANDING → STAGING → CORE → MARTS → BI_* SERVING VIEWS**.

For **LANDING**, show the six typed ingestion tables produced from Silver Parquet and emphasize file-level audit metadata (`_file_name`, `_file_row_number`, loaded timestamp). Label the responsibility **“preserve curated physical ingestion evidence”**.

For **STAGING**, show six dbt staging views and label **“normalize names/types; select authoritative logical observations; preserve provenance”**.

For **CORE**, show `dim_track`, `dim_artist`, `dim_album`, `dim_playlist`, `bridge_track_artist`, and `fact_playlist_snapshot`. Visually highlight the canonical fact grain **`(playlist_id, snapshot_date, track_position)`** and label `pipeline_run_id` as **physical lineage only — not part of analytical uniqueness**.

For **MARTS**, show the four analytical models: playlist trends, track lifecycle, playlist changes, artist presence. Label them **“business/analytical grains, still warehouse semantics”**.

For **BI_* SERVING VIEWS**, list `BI_PLAYLIST_DAILY`, `BI_TRACK_DAILY`, `BI_TRACK_CHANGES`, `BI_ARTIST_DAILY`. Add a small semantic-contract box: one-based display positions, explicit null semantics, ratios from 0–1, provenance retained, tool-agnostic consumption.

Add a thin lower rail explaining replay semantics: **new physical `pipeline_run_id` → fresh immutable evidence → dbt selects authoritative logical observation → merge converges on stable business grain**.

Do not show Power BI as implemented. Do not imply that physical run IDs create new business facts. The diagram should make the separation between physical lineage and logical analytics immediately obvious.

---

## 18 — Implemented and deferred extensions (integrated)

**Saved as:** `docs/assets/architecture/implemented-deferred-extensions.png`

**Placement:** `docs/ARCHITECTURE.md → Scope Boundaries and Deferred Components`

### Regeneration brief

Match the same white-background, 16:9, thin-outline, rounded-card visual system used by the first two approved diagrams. Arrange three separately titled panels: **A. Implemented live-source path** (dashed Spotify Web API → AWS Lambda → S3 Bronze, explicitly outside the bounded public demo); **B. Terraform / IaC boundary** (S3, IAM, Lambda, Glue and monitoring/budget desired-state modules, validated offline/CI with no claim of apply/import/destroy or state ownership of existing live resources); and **C. Power BI / BI artifacts** (semantic model and dashboard marked *Deferred from v1.0.0*). Use a compact status legend for validated, contract-tested, deferred and optional paths. Do not depict Terraform as a step in the live data flow or Power BI as a validated consumer.
