# Cost Strategy & Budget Governance

This document establishes the financial and operational guardrails for the Spotify Analytics Data Platform.

---

## 1. Portfolio Budget Target

| Metric | Target Limit | Governance Type | Notes |
| :--- | :--- | :--- | :--- |
| **Monthly Budget Target** | **≤ $20.00 USD / month** | **Operational planning target** | AWS budget enforcement is not deployed yet. |
| **Target Steady-State (Idle)** | Not yet measured | Cloud validation pending | Architecture is designed to avoid always-on compute. |
| **Single Full Pipeline Run** | Not yet measured | Cloud validation pending | Must be measured in the target AWS/Snowflake accounts. |

> [!IMPORTANT]
> The $20.00/month figure is an **operational portfolio planning target**, not a hard cloud
> provider stop guarantee. The repository currently contains Snowflake cost-control SQL
> contracts but no deployed AWS Budget, Terraform teardown automation, or measured run-cost
> evidence. Any vendor pricing examples below are planning inputs only and must be rechecked
> before provisioning.

---

## 2. Architectural Cost Principles

1. **Zero Always-On Compute**: No permanently running EC2 instances, EMR clusters, or Kubernetes nodes. Compute is provisioned ephemerally or invoked serverless.
2. **Aggressive Auto-Suspend**: Snowflake virtual warehouses auto-suspend after 60 seconds of inactivity.
3. **Local-First Development**: Airflow 3.x, unit tests, and PySpark transformations run locally in Docker or Python virtualenvs. Cloud services are invoked only for integration verification and portfolio demonstrations.
4. **No Managed Cloud Orchestrator (No MWAA)**: AWS MWAA (Managed Workflows for Apache Airflow) incurs a baseline cost of ~$0.49/hour (~$350/month estimated base). MWAA is explicitly excluded; Airflow runs in Docker locally or via on-demand triggers.
5. **No NAT Gateways**: AWS NAT Gateways incur an estimated baseline of ~$0.045/hour (~$32/month base) plus data processing fees. Lambda functions run outside VPC to eliminate NAT Gateway requirements.
6. **Reproducible Ephemeral Infrastructure**: Terraform implementation is planned in M8. Until then, no claim is made that all cloud resources can be created or destroyed reproducibly from this repository.

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
| **Snowflake Warehouse Left Running** | Failing to set `AUTO_SUSPEND` drains credits. | SQL contract sets `AUTO_SUSPEND = 60`; live deployment pending. |
| **Unbounded CloudWatch Logs** | Unlimited retention can accumulate cost. | Seven-day retention is an M8 infrastructure target; not deployed today. |

---

## 4. Operating Modes

### Mode 1: Development Mode (Current Default)
- No live-cloud spend is required for the repository's current validation path.
- Core Python tests run locally on Python 3.12.
- PySpark transformations run locally on the Glue 5.1 parity stack (Python 3.11 / Spark 3.5.6 / Java 17).
- Snowflake SQL and dbt project structure are validated offline without a warehouse connection.
- Synthetic fixtures are the default source material.

### Mode 2: Demonstration / Portfolio Review Mode (Target)
- Cloud infrastructure is provisioned only after M8 Terraform and budget guardrails exist.
- Portfolio analytics uses fully synthetic histories per ADR-0008.
- AWS Lambda/S3/Glue and Snowflake/Snowpipe/dbt are exercised as a vertical slice with measured cost and teardown evidence.
- Power BI consumes validated Snowflake marts only after the warehouse build succeeds.

### Mode 3: Extended Production-Like Mode (Future Reference)
- Not implemented and not required for the portfolio vertical slice.
- Any recurring schedule, lifecycle policy, or anomaly detection must be separately costed and validated before enabling it.

---

## 5. Cost Governance & Alarms

1. **AWS Budgets (M8 target)**:
   - Terraform will define alerts at **$10.00 USD** and **$18.00 USD** before the cloud demo path is considered ready.
   - The current repository does not claim that these alerts already exist in an AWS account.
2. **Snowflake Resource Monitors**:
   - M4 SQL contracts define a resource monitor attached to `COMPUTE_WH` with:
     - Notification at 80% of monthly credit quota.
     - Immediate suspension at 100% of quota.
   - Live deployment and account-specific notification behavior remain cloud-validation gates.

---

## 6. Cost Teardown Checklist

Before completing any live cloud demonstration or testing phase:

- [ ] Run `terraform destroy` in `infra/terraform/` to decommission AWS resources (Lambda, Glue jobs, S3 buckets, log groups).
- [ ] Confirm in Snowflake Web UI that `COMPUTE_WH` is in `SUSPENDED` state.
- [ ] Verify that no lingering Snowpipe or task is running queries in `SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY`.
- [ ] Check AWS Billing Console -> Cost Explorer for any unexpected active services.
- [ ] Verify S3 buckets are empty or archived if destroying the environment.
