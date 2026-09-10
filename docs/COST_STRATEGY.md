# Cost Strategy & Budget Governance

## 1. Status and budget target

The **USD 20/month** figure is an operational portfolio planning target, not a hard
cross-provider spending cap. This repository has no Terraform implementation or
validated cloud billing evidence. Budgets, warehouse monitors, lifecycle rules,
and teardown automation below are planned controls.

Earlier documentation included idle, per-run, and monthly dollar estimates and
assumed Free Tier coverage. Those figures were not backed by measurements or a
current account-specific quote. They are not retained as spending promises.
Use synthetic data for demonstrations under
[ADR-0008](adr/0008-synthetic-analytics-and-source-use-boundary.md).

## 2. Planned cost controls

| Area | Intended control | Limitation / current state |
| --- | --- | --- |
| Development | Current Python tests run offline; future Spark/Airflow run locally | Spark and Compose environments are not implemented |
| AWS orchestration | Local Airflow instead of MWAA | No current price comparison or savings measurement |
| AWS network | Avoid an unnecessary NAT Gateway or always-on EC2 | Infrastructure design still requires implementation review |
| Lambda | On-demand execution with bounded duration and retries | No live duration, memory, or request benchmark |
| Glue | On-demand jobs and measured worker/runtime sizing | No job deployed or billed run measured |
| Snowflake warehouse | X-Small, AUTO_SUSPEND=60, AUTO_RESUME=TRUE | Planned settings; idle/resume billing must be included |
| Snowpipe and storage | Monitor ingestion, stored bytes, and requests separately | Warehouse suspension does not suspend every serverless/storage charge |
| Logs | Seven-day CloudWatch retention | Not configured; ingestion charges still apply |
| Secrets | Minimal secret count and API requests | No persisted live secret or verified entitlement |

## 3. Build a workload-based estimate before deployment

Record region, currency, estimate date, account/trial eligibility, and applicable
rates from official pricing pages. A useful worksheet should include:

- **Lambda:** invocation count plus memory in GB multiplied by billed seconds;
  include throttling waits and retries rather than assuming every run is short.
- **Glue:** workers/DPUs multiplied by billed runtime, including startup, minimum
  billing, retries, and actual worker-type rules.
- **Snowflake:** warehouse credits multiplied by the account's price per credit;
  include resumes, idle time before suspension, and service-specific minimums.
- **Snowpipe:** account-applicable serverless ingestion charges, separately from
  warehouse credits; do not model it as free because the warehouse is suspended.
- **Storage and APIs:** Bronze/Silver retention, object requests, transfer, logs,
  and secret storage/access. Append-only run history adds storage over time.

Apply credits or free allowances only after verifying eligibility and unused
account allowance. Reconcile estimated versus actual usage after a permitted
test deployment. No billing check is performed by `make check`.

## 4. Planned operating modes

1. **Current local development:** offline synthetic pytest fixtures and Python
   tooling. No cloud services are invoked by the test suite.
2. **Future synthetic end-to-end demonstration:** implement a synthetic ingestion
   path, persist raw histories, then exercise Glue, Snowflake, dbt, and Power BI
   only after the corresponding milestones and deployment authorization.
3. **Future scheduled synthetic runs:** define cadence, retention, and run budgets
   from measured usage. Live analytical use is outside the current demo decision.

None of these modes has an established monthly cloud bill in this repository.

## 5. Planned alert thresholds

- AWS Budgets alerts at **USD 10** and **USD 18** remain proposed M8 thresholds.
  They cover the configured AWS billing scope, not Snowflake charges. Notifications
  may lag usage and do not stop all services at USD 20.
- A future Snowflake resource monitor can notify/suspend its covered warehouse
  usage. It is not an account-wide cap on serverless ingestion and storage.
- The operator must reconcile AWS and Snowflake spending against the combined
  portfolio target and decide whether to stop subsequent runs.

## 6. Teardown verification after future deployments

Once reviewed Terraform manifests exist, inspect the destroy plan and the exact
resources/data affected before applying it. Verify resource removal, warehouse
suspension, retained objects, serverless activity, and subsequent billing. A
successful destroy command does not prove zero residual charges or delete every
resource outside its managed state. No teardown command is currently runnable
from this README alone.

## Pricing references

Verify current rates before using them in an estimate:
- [AWS Lambda pricing](https://aws.amazon.com/lambda/pricing/)
- [AWS Glue pricing](https://aws.amazon.com/glue/pricing/)
- [Amazon S3 pricing](https://aws.amazon.com/s3/pricing/)
- [Amazon CloudWatch pricing](https://aws.amazon.com/cloudwatch/pricing/)
- [AWS Secrets Manager pricing](https://aws.amazon.com/secrets-manager/pricing/)
- [Snowflake cost categories](https://docs.snowflake.com/en/user-guide/cost-understanding-overall)
