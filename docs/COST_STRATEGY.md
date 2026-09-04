# Cost Strategy & Budget Governance

This document establishes the financial and operational guardrails for the Spotify Analytics Data Platform.

---

## 1. Portfolio Budget Target

| Metric | Target Limit | Notes |
| :--- | :--- | :--- |
| **Monthly Operating Ceiling** | **≤ $20.00 USD / month** | Hard ceiling for regular portfolio evaluation and testing. |
| **Target Steady-State (Idle)** | **$0.00 - $2.00 USD / month** | When pipelines are not actively running. |
| **Single Full Integration Run** | **< $0.25 USD / run** | End-to-end extraction, Glue ETL, and Snowflake load. |

> [!IMPORTANT]
> The $20.00/month budget is a strict portfolio management target, not a cloud provider price guarantee. All numeric figures below are conservative estimates based on official public documentation and typical consumption patterns.

---

## 2. Architectural Cost Principles

1. **Zero Always-On Compute**: No permanently running EC2 instances, EMR clusters, or Kubernetes nodes. Compute is provisioned ephemerally or invoked serverless.
2. **Aggressive Auto-Suspend**: Snowflake virtual warehouses auto-suspend after 60 seconds of inactivity.
3. **Local-First Development**: Airflow, unit tests, and PySpark transformations run locally in Docker or Python virtualenvs. Cloud services are invoked only for integration verification and portfolio demonstrations.
4. **No Managed Orchestrator in Early Phases**: AWS MWAA (Managed Workflows for Apache Airflow) incurs a baseline cost of ~$0.49/hour (~$350/month) for a base environment. MWAA is explicitly excluded; Airflow runs in Docker locally or via on-demand triggers.
5. **No NAT Gateways**: AWS NAT Gateways cost ~$0.045/hour plus data transfer charges (~$32/month base). Lambda functions run outside VPC or use public endpoints to eliminate NAT Gateway requirements.
6. **Reproducible Ephemeral Infrastructure**: All cloud infrastructure is declared in Terraform and can be spun up for live demos and immediately destroyed (`terraform destroy`).

---

## 3. Cost Component Categorization

### A. Expected Low-Cost / Free Tier Components

- **Amazon S3**:
  - Storage: < 1 GB of raw JSON and Parquet per month (< $0.03/month).
  - API Requests: Standard GET/PUT requests fall well within the AWS Free Tier (20,000 GET, 2,000 PUT/month).
- **AWS Lambda**:
  - Execution: Ingesting 5 playlists daily requires ~5 invocations/day, each executing for < 15 seconds with 256 MB RAM.
  - Cost: Free tier covers 1,000,000 requests and 3,200,000 seconds of compute time per month. Estimated cost: $0.00.
- **Amazon CloudWatch**:
  - Log ingestion: < 50 MB/month with a 7-day retention policy. Capped well within the 5 GB free tier.
- **AWS Secrets Manager**:
  - 1 secret (Spotify API credentials) = $0.40/month per secret + negligible API call fees.
- **GitHub Actions**:
  - Free tier for public repositories includes 2,000 free minutes/month for CI (linting and unit tests).

### B. Controlled Variable Cost Components

- **AWS Glue (PySpark)**:
  - Billed per DPU-Hour (Data Processing Unit) with a 1-minute minimum.
  - A standard Glue 4.0 job configured with 2 DPUs running for 2 minutes consumes `(2 DPUs * 2/60 hrs) = 0.067 DPU-hours`.
  - At ~$0.44 per DPU-hour (US East), each run costs approximately ~$0.03. Running daily = ~$0.90/month.
- **Snowflake (Data Warehouse)**:
  - Billed per credit per second (Standard Edition: 1 credit/hour for X-Small warehouse).
  - An `X-Small` warehouse consumes 1 credit/hour (~$2.00 to $3.00 per credit depending on contract/edition).
  - With `AUTO_SUSPEND = 60`, a daily dbt run executing in 90 seconds consumes ~150 billed seconds (~0.042 credits, or ~$0.10/run).
  - Free trial accounts provide $400 of trial credits for initial implementation.

### C. Dangerous Cost Traps (Explicitly Avoided)

| Component | Why It Is Dangerous | Status in This Project |
| :--- | :--- | :--- |
| **AWS MWAA** | Base environment costs ~$350/month continuously. | **Prohibited** (Use Local Docker Airflow). |
| **AWS NAT Gateway** | Base charge ~$32/month per AZ + data transfer. | **Prohibited** (Lambda operates outside VPC). |
| **Amazon EMR** | Cluster nodes billed continuously unless terminated. | **Prohibited** (Use AWS Glue on-demand). |
| **Amazon Redshift Serverless** | Minimum RPU baseline can accumulate rapidly. | **Prohibited** (Use Snowflake X-Small). |
| **Snowflake Warehouse Left Running** | Failing to set `AUTO_SUSPEND` drains credits. | **Enforced `AUTO_SUSPEND = 60`**. |
| **Unbounded CloudWatch Logs** | Default retention is `Never Expire`. | **Enforced 7-day retention**. |

---

## 4. Operating Modes

### Mode 1: Development Mode (Default)
- Target cost: **$0.00 - $1.00 / month**
- Airflow runs locally via Docker Compose.
- PySpark transformations tested locally using pytest and local Spark sessions.
- Mock JSON data generated locally using `scripts/generate_mock_spotify_data.py`.
- Snowflake queries executed against local DuckDB or transient Snowflake trial accounts.

### Mode 2: Demonstration / Portfolio Review Mode
- Target cost: **$2.00 - $5.00 / month**
- Cloud infrastructure provisioned via Terraform.
- Live Spotify API ingestion via AWS Lambda into S3 Bronze.
- AWS Glue job triggered once daily via Airflow.
- Snowpipe ingests into Snowflake Landing.
- dbt Core runs transformations on Snowflake `X-Small` warehouse.
- Power BI connects to Snowflake Marts.

### Mode 3: Future Production-Grade Mode (Reference)
- Target cost: **$15.00 - $20.00 / month**
- Continuous daily scheduling across 10-20 playlists.
- S3 lifecycle policies archiving bronze data to Glacier Instant Retrieval after 90 days.
- CloudWatch anomaly detection alarms monitoring job execution duration.

---

## 5. Cost Governance & Alarms

1. **AWS Budgets**:
   - A zero-cost AWS Budget must be created via Terraform or AWS Console with an alert threshold set at **$10.00 USD** (50% of budget) and **$18.00 USD** (90% of budget).
   - Email alerts configured to notify the platform administrator immediately.
2. **Snowflake Resource Monitors**:
   - A Snowflake Resource Monitor attached to `COMPUTE_WH` configured with:
     - Warning at 80% of monthly quota (e.g., 5 credits).
     - Suspend immediately at 100% of monthly quota.

---

## 6. Cost Teardown Checklist

Before completing any live cloud demonstration or testing phase:

- [ ] Run `terraform destroy` in `infra/terraform/` to decommission AWS resources (Lambda, Glue jobs, S3 buckets, log groups).
- [ ] Confirm in Snowflake Web UI that `COMPUTE_WH` is in `SUSPENDED` state.
- [ ] Verify that no lingering Snowpipe or task is running queries in `SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY`.
- [ ] Check AWS Billing Console -> Cost Explorer for any unexpected active services.
- [ ] Verify S3 buckets are empty or archived if destroying the environment.
