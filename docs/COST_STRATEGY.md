# Cost Strategy & Budget Governance

The v1.0.0 cost model is designed around **bounded demonstrations, serverless/on-demand compute, fast suspension, and explicit budget guardrails**. The project treats cost as an engineering constraint: every live validation should have a finite scope, measurable usage, and a clear stop condition.

> **Evidence boundary**
>
> The repository contains a reusable Terraform stack with a **USD 20/month AWS Budget default** and actual + forecast notifications at **50%** and **90%**. That Terraform stack is implemented and validated offline/CI. The bounded v1.0.0 live demo used a separately created **USD 5/month AWS Budget**. No Terraform `apply` or `destroy` was executed against that validated demo environment, so this repository does not claim Terraform state ownership of those live resources.

> **Visual placeholder — Cost governance and measured usage**
> Target asset: `docs/assets/cost/cost-governance-evidence.png`
> Production brief: [`docs/assets/README.md`](assets/README.md), section **Cost governance and evidence**.

---

## 1. Cost Control Model

The platform uses three complementary control layers:

| Layer | v1.0.0 control | Purpose |
| --- | --- | --- |
| **Architecture** | Local Airflow, no MWAA, no NAT Gateway, no always-on EC2/EMR, bounded Glue, one Snowflake X-Small warehouse | Avoid fixed infrastructure that can spend while the portfolio is idle |
| **Runtime guardrails** | Lambda reserved concurrency `1`; Glue `FLEX`, 2 × `G.1X`, one concurrent run, 15-minute timeout; Snowflake `AUTO_SUSPEND = 60` | Bound the blast radius of accidental or repeated execution |
| **Budget / quota controls** | Live demo AWS Budget at USD 5; reusable Terraform default at USD 20 with 50/90 actual + forecast alerts; Snowflake resource monitor at 2 credits/month | Create early warning and hard compute-stop behavior where the provider supports it |

AWS Budgets are **notification controls**, not hard account shutoffs. The Snowflake resource monitor is different: it notifies at 80% of its 2-credit monthly quota and uses `SUSPEND_IMMEDIATE` at 100% for `COMPUTE_WH`.

---

## 2. Architectural Cost Decisions

### Local-first orchestration

Apache Airflow 3 runs in Docker for development and bounded demonstrations. The project intentionally does not use AWS MWAA, which would introduce an always-on managed-orchestrator baseline that is unnecessary for this portfolio workload.

### Serverless / on-demand AWS compute

- **AWS Lambda** is invoked only for the optional live-source extraction path. Terraform constrains the function to 256 MB by default, a 30-second timeout, and reserved concurrency `1`.
- **AWS Glue 5.1** performs technical Bronze-to-Silver curation only when a run is submitted. Terraform defaults to `FLEX`, two `G.1X` workers, one concurrent run, no automatic Glue retry, and a 15-minute timeout.
- **Amazon S3** is the only persistent AWS data plane in the reusable stack. One private, versioned bucket holds `bronze/`, `silver/`, `artifacts/`, and `metadata/` prefixes. Non-current versions expire after 30 days and incomplete multipart uploads are aborted after seven days.
- **CloudWatch Logs** are retained for seven days in the reusable development stack. They are operational telemetry, not a long-term compliance archive.

### No NAT Gateway dependency

The Lambda source path is not placed in a VPC. Its dependency is the public Spotify API, and forcing that path through private subnets would add NAT Gateway or VPC-endpoint cost without protecting a private backend dependency in this bounded architecture.

### Snowflake compute is deliberately small and suspendable

`COMPUTE_WH` is defined as a single-cluster **X-Small** warehouse with:

- `AUTO_SUSPEND = 60`
- `AUTO_RESUME = TRUE`
- `INITIALLY_SUSPENDED = TRUE`
- 120-second queued-statement timeout
- 900-second statement timeout
- `SPOTIFY_DEV_MONITOR` attached as a 2-credit/month resource monitor

The monitor notifies at 80% and suspends the warehouse immediately at 100%. It governs warehouse credits; it is not a dollar-denominated guarantee and does not meter serverless Snowpipe usage.

---

## 3. Budget Guardrails: Live Demo vs Reusable Terraform

These are intentionally distinct evidence domains:

| Guardrail | Value | Status | Interpretation |
| --- | ---: | --- | --- |
| **AWS Budget used during bounded live demo** | **USD 5/month** | Live, manually created | Protected the actual validation account during the bounded demo window |
| **Terraform AWS Budget default** | **USD 20/month** | Implemented; validated offline/CI | Reusable desired-state default for future Terraform-owned deployments |
| Terraform alert 1 | 50% actual | Implemented | Email notification |
| Terraform alert 2 | 50% forecast | Implemented | Email notification |
| Terraform alert 3 | 90% actual | Implemented | Email notification |
| Terraform alert 4 | 90% forecast | Implemented | Email notification |

The USD 20 Terraform value is a **portfolio planning ceiling**, not evidence that the validated demo account was configured with that exact budget. Conversely, the manually created USD 5 demo budget proves a live cost guardrail existed, but it does not prove Terraform created or owned it.

---

## 4. Measured v1.0.0 Usage Evidence

The project records cloud **usage evidence** because it is portable and auditable across pricing plans. It does not convert these measurements into an isolated per-run dollar figure without complete provider billing context.

| Service | Measured evidence | Scope | What it proves | What it does **not** prove |
| --- | ---: | --- | --- | --- |
| **AWS Glue 5.1** | **589 DPU-seconds** | Four successful Airflow-orchestrated validation runs: the bounded three-day slice plus one-day replay | The real Glue path executed with bounded compute and measurable resource consumption | An exact dollar cost for a single run or month |
| **Snowflake** | **0.45 cumulative credits** | Resource-monitor reading after the final bounded validation/replay | The warehouse workload consumed a small, observable amount of cumulative compute under the resource monitor | An isolated dbt-run cost, an account-wide bill, or serverless Snowpipe cost |

Why the distinction matters:

- Glue pricing depends on region, worker configuration, billing minimums, and the exact execution window.
- Snowflake credit pricing depends on account edition, cloud/region, and commercial terms.
- The `0.45` reading is **cumulative since resource-monitor creation**, so attributing all of it to one pipeline run would be incorrect.
- Snowpipe is serverless and is outside the warehouse resource-monitor quota.

These measurements should therefore be cited as **evidence of bounded usage**, not as standalone dollar-cost claims.

---

## 5. Operating Modes

### Offline / development mode

The default engineering loop does not require cloud spend:

- Python 3.12 tests and static checks run locally/CI.
- Glue transformation contracts run on the local Spark 3.5.6 / Python 3.11 parity stack.
- Snowflake SQL and dbt structure are parsed and contract-tested offline.
- Airflow runs locally in Docker.
- Terraform is checked with formatting, backend-free initialization, validation, TFLint, and Checkov without cloud credentials.

### Bounded live validation mode

The v1.0.0 live evidence intentionally exercised only the minimum vertical slice required to prove cloud integration behavior. The demo used a manually controlled AWS/Snowflake environment, a USD 5 AWS Budget, an X-Small Snowflake warehouse with 60-second auto-suspend, and the Snowflake resource monitor described above.

The bounded live path produced real S3/Glue/Snowflake/dbt/Airflow evidence. That does **not** extend the ownership claim to every reusable Terraform resource or to the optional live Spotify/Lambda source path.

### Future Terraform-owned deployment

The reusable stack is ready to become the source of AWS desired state for a fresh environment. A future operator can supply deployment-specific variables, review `terraform plan`, and explicitly choose whether to apply it. Only after such an apply, with retained state and reconciliation of any pre-existing resources, would it be correct to describe that environment as Terraform-owned.

---

## 6. Cost-Safe Teardown and Stop Conditions

Before ending any live validation session:

- [ ] Confirm `COMPUTE_WH` is `SUSPENDED` in Snowflake.
- [ ] Confirm no unexpected warehouse queries or tasks are continuing to execute.
- [ ] Review the Snowflake resource monitor and record cumulative usage evidence.
- [ ] Review AWS Billing / Cost Explorer for unexpected active services.
- [ ] Confirm no Glue job run remains active.
- [ ] For a manually created demo environment, delete or disable resources through the same controlled process that created them and record what was checked.
- [ ] For a future Terraform-owned environment, review the plan/state boundary before running `terraform destroy`; never use the v1.0.0 repository history as evidence that destroy was already exercised on the validated demo.

The goal is simple: a portfolio demo should leave behind **evidence**, not unattended compute.
