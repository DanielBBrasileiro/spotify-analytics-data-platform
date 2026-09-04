# Cost Strategy & Budget Governance

This document establishes the financial and operational guardrails for the Spotify Analytics Data Platform.

---

## 1. Portfolio Budget Target

| Metric | Target Limit | Governance Type | Notes |
| :--- | :--- | :--- | :--- |
| **Monthly Budget Target** | **≤ $20.00 USD / month** | **Operational Target & Alert Threshold** | Target ceiling for portfolio demonstration runs. |
| **Target Steady-State (Idle)** | **$0.00 - $2.00 USD / month** | Estimated Range | When pipelines and warehouses are suspended. |
| **Single Full Pipeline Run** | **< $0.25 USD / run** | Estimated Execution Cost | Ephemeral Lambda, Glue 5.1 job, and dbt merge run. |

> [!IMPORTANT]
> The $20.00/month figure is an **operational portfolio budget target and alert threshold**, not a hard cloud provider stop guarantee. Cloud billing alarms notify operators when thresholds are crossed but do not instantaneously cut off all running services without configured automated shutdown scripts. All numeric figures below are conservative estimates based on official documentation and typical consumption patterns.

---

## 2. Architectural Cost Principles

1. **Zero Always-On Compute**: No permanently running EC2 instances, EMR clusters, or Kubernetes nodes. Compute is provisioned ephemerally or invoked serverless.
2. **Aggressive Auto-Suspend**: Snowflake virtual warehouses auto-suspend after 60 seconds of inactivity.
3. **Local-First Development**: Airflow 3.x, unit tests, and PySpark transformations run locally in Docker or Python virtualenvs. Cloud services are invoked only for integration verification and portfolio demonstrations.
4. **No Managed Cloud Orchestrator (No MWAA)**: AWS MWAA (Managed Workflows for Apache Airflow) incurs a baseline cost of ~$0.49/hour (~$350/month estimated base). MWAA is explicitly excluded; Airflow runs in Docker locally or via on-demand triggers.
5. **No NAT Gateways**: AWS NAT Gateways incur an estimated baseline of ~$0.045/hour (~$32/month base) plus data processing fees. Lambda functions run outside VPC to eliminate NAT Gateway requirements.
6. **Reproducible Ephemeral Infrastructure**: All cloud infrastructure is declared in Terraform and can be spun up for live demos and immediately destroyed (`terraform destroy`).

---

## 3. Cost Component Categorization

### A. Expected Low-Cost / Free Tier Components

- **Amazon S3**:
  - Storage: < 1 GB of raw JSON and Parquet per month (< $0.03/month estimated).
  - API Requests: Standard GET/PUT requests fall well within the AWS Free Tier.
- **AWS Lambda**:
  - AWS Lambda Free Tier includes **400,000 GB-seconds** of compute time and **1 million requests** per month (perpetual free tier).
  - Ingesting monitored playlists daily requires minimal invocations (< 30 seconds per run with 256 MB RAM = < 8 GB-seconds per day). Estimated cost: $0.00.
- **Amazon CloudWatch**:
  - Log ingestion: < 50 MB/month with a strict 7-day retention policy. Capped well within the 5 GB free tier.
- **AWS Secrets Manager**:
  - 1 secret (Spotify API credentials) = ~$0.40/month per secret + negligible API call fees.
- **GitHub Actions**:
  - For public open-source GitHub repositories, standard GitHub-hosted Linux runners are provided free of charge under standard GitHub service terms.

### B. Controlled Variable Cost Components

- **AWS Glue 5.1 (PySpark)**:
  - Billed per DPU-Hour (Data Processing Unit) with a 1-minute minimum.
  - An estimated Glue 5.1 job configured with 2 DPUs running for ~2 minutes consumes `(2 DPUs * 2/60 hrs) = 0.067 DPU-hours` (estimated ~$0.03 to $0.05 per run based on regional pricing). Running daily equals ~$0.90 to $1.50/month.
- **Snowflake (Data Warehouse)**:
  - Billed per credit per second (Standard Edition consumes 1 credit/hour for an `X-Small` warehouse).
  - Credit dollar rates vary depending on contractual tier and cloud region.
  - With `AUTO_SUSPEND = 60` and `AUTO_RESUME = TRUE`, a daily dbt run executing in 60-90 seconds consumes ~120-150 billed seconds (~0.033 to 0.042 credits).
  - Trial credits may be available depending on the current Snowflake trial program terms.

### C. Dangerous Cost Traps (Explicitly Avoided)

| Component | Why It Is Dangerous | Status in This Project |
| :--- | :--- | :--- |
| **AWS MWAA** | Base environment incurs ~$350/month continuously. | **Prohibited** (Use Local Docker Airflow). |
| **AWS NAT Gateway** | Base charge ~$32/month per AZ + data transfer fees. | **Prohibited** (Lambda operates outside VPC). |
| **Amazon EMR** | Cluster nodes billed continuously unless terminated. | **Prohibited** (Use AWS Glue on-demand). |
| **Amazon Redshift Serverless** | Minimum RPU baseline can accumulate rapidly. | **Prohibited** (Use Snowflake X-Small). |
| **Snowflake Warehouse Left Running** | Failing to set `AUTO_SUSPEND` drains credits. | **Enforced `AUTO_SUSPEND = 60`**. |
| **Unbounded CloudWatch Logs** | Default retention is `Never Expire`. | **Enforced 7-day retention**. |

---

## 4. Operating Modes

### Mode 1: Development Mode (Default)
- Target cost: **$0.00 - $1.00 / month**
- Airflow 3.x runs locally via Docker Compose.
- PySpark transformations tested locally using pytest and local Spark sessions.
- Mock JSON data generated locally matching current 2026 API schemas.
- Snowflake queries executed against local DuckDB or transient Snowflake accounts.

### Mode 2: Demonstration / Portfolio Review Mode
- Target cost: **$2.00 - $5.00 / month**
- Cloud infrastructure provisioned on-demand via Terraform.
- Live Spotify API ingestion via AWS Lambda into S3 Bronze.
- AWS Glue 5.1 job triggered once daily via Airflow.
- Snowpipe ingests into Snowflake Landing.
- dbt Core runs incremental merges on Snowflake `X-Small` warehouse.
- Power BI connects to Snowflake Marts.

### Mode 3: Extended Production-Like Mode (Reference)
- Target cost: **$15.00 - $20.00 / month**
- Daily scheduling across monitored playlists.
- S3 lifecycle policies archiving bronze data after 90 days.
- CloudWatch anomaly detection alarms monitoring job execution duration.

---

## 5. Cost Governance & Alarms

1. **AWS Budgets**:
   - An AWS Budget configured via Terraform with alert thresholds set at **$10.00 USD** (50% of target) and **$18.00 USD** (90% of target).
   - Email notifications alert the administrator proactively before approaching the $20/month threshold.
2. **Snowflake Resource Monitors**:
   - A Snowflake Resource Monitor attached to `COMPUTE_WH` configured with:
     - Notification at 80% of monthly credit quota.
     - Immediate suspension at 100% of quota.

---

## 6. Cost Teardown Checklist

Before completing any live cloud demonstration or testing phase:

- [ ] Run `terraform destroy` in `infra/terraform/` to decommission AWS resources (Lambda, Glue jobs, S3 buckets, log groups).
- [ ] Confirm in Snowflake Web UI that `COMPUTE_WH` is in `SUSPENDED` state.
- [ ] Verify that no lingering Snowpipe or task is running queries in `SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY`.
- [ ] Check AWS Billing Console -> Cost Explorer for any unexpected active services.
- [ ] Verify S3 buckets are empty or archived if destroying the environment.
