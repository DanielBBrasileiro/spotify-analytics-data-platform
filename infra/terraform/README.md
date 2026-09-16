# AWS Infrastructure as Code

This Terraform root defines the reusable AWS infrastructure contract for Spotify Analytics Data Platform v1.0.0. The stack is **implemented and validated offline/CI**; it has **not** been applied to, imported from, or destroyed against the bounded live demo environment used to capture v1.0.0 evidence.

> **Ownership boundary**
>
> Terraform describes the intended AWS resource shape and least-privilege relationships. The live demo resources were controlled separately. Because no `terraform apply`, import, or `terraform destroy` was performed for that environment, the repository does not claim that the current Terraform state owns those live resources.

> **Visual placeholder — Terraform scope and validation boundary**
> Target asset: `docs/assets/terraform/terraform-scope-validation.png`
> Production brief: [`docs/assets/README.md`](../../docs/assets/README.md), section **Terraform scope and validation boundary**.

---

## 1. Reusable Resource Shape

The root composes focused modules for S3, IAM, Lambda, Glue, and monitoring/budget controls.

| Domain | Terraform resource shape | Cost / security intent |
| --- | --- | --- |
| **Lake** | One S3 bucket with `bronze/`, `silver/`, `artifacts/`, and `metadata/` prefixes | Small persistent footprint; one policy surface; lifecycle-bounded versions |
| **Ingestion** | Python 3.12 Lambda, 256 MB default, 30-second timeout, reserved concurrency `1` | Optional source path with bounded concurrency and no always-on compute |
| **Curation** | Glue 5.1 Spark job, `FLEX`, 2 × `G.1X` default, one concurrent run, 15-minute timeout | On-demand transformation with explicit compute limits |
| **Observability** | Lambda and standard Glue CloudWatch log groups, seven-day retention | Operational telemetry without long-lived log accumulation |
| **Cost governance** | AWS Budget, USD 20/month default, configurable email | Actual + forecast alerts at 50% and 90% |
| **Snowflake integration** | AWS IAM role trusted by one configured Snowflake IAM user plus external ID | Cross-account Silver read without static AWS credentials |

Taggable resources inherit these defaults:

```text
Project     = SpotifyAnalyticsDataPlatform
Environment = dev
ManagedBy   = Terraform
```

The stack deliberately excludes NAT Gateways, EC2, managed databases, EMR clusters, and other always-on infrastructure from this bounded portfolio shape.

---

## 2. S3 Lake Security and Lifecycle

The lake module creates one bucket with the following controls:

- all four S3 public-access-block settings enabled;
- `BucketOwnerEnforced` object ownership;
- SSE-S3 (`AES256`) encryption at rest;
- versioning enabled;
- an explicit bucket-policy deny for non-TLS requests;
- incomplete multipart uploads aborted after seven days;
- non-current object versions expired after 30 days;
- `force_destroy = true` by default for this development/portfolio stack so a deliberate future Terraform destroy can remove versioned runtime artifacts instead of leaving billable objects behind.

SSE-S3 is an intentional low-cost development choice. The stack does not claim customer-managed KMS keys, cross-region replication, or a second S3 access-log bucket as v1.0.0 requirements.

---

## 3. IAM Least-Privilege Model

The IAM module avoids wildcard **allow** actions for sensitive workload permissions and scopes access by service, bucket prefix, resource ARN, and trust principal.

### Lambda execution role

The Lambda role can:

- `s3:PutObject` only to `bronze/spotify/*`;
- `secretsmanager:GetSecretValue` only for the configured Spotify secret ARN;
- `logs:CreateLogStream` and `logs:PutLogEvents` only for its Terraform-created CloudWatch log group.

It cannot read or delete lake data, write the Spotify secret, or manage IAM resources.

### Glue execution role

The Glue role can:

- inspect the lake bucket location;
- list only the Bronze, Silver, Glue-artifact, and metadata prefixes;
- read Bronze and `artifacts/glue/*` objects;
- read/write/delete Silver objects as required by the curated dataset writer;
- read/write completion metadata;
- write streams/events only to the configured Glue log groups.

### Snowflake storage role

The Snowflake role trust policy requires both:

1. the exact Snowflake-generated AWS IAM user ARN; and
2. the configured `sts:ExternalId`.

Its data-plane permissions are read-only and restricted to `silver/*`: bucket location, prefix-scoped listing, `GetObject`, and `GetObjectVersion`.

The broad `s3:*` visible in the S3 module exists only in an explicit **Deny** statement conditioned on insecure transport. It is not an allow grant.

---

## 4. Secret and Runtime Artifact Boundaries

Terraform does **not** create or store the Spotify secret value. The root accepts the ARN of an existing Secrets Manager secret whose JSON contract is:

```json
{
  "client_id": "...",
  "client_secret": "...",
  "refresh_token": "..."
}
```

The Lambda environment contains the **secret ARN**, not the credential values themselves.

Terraform also does not build deployment artifacts. Before a future apply, the referenced objects must exist in the lake artifact prefix, or their keys must be overridden:

```text
artifacts/lambda/spotify-ingestion.zip
artifacts/glue/bronze_to_silver_curation.py
artifacts/glue/spotify-glue-lib.zip
```

The Lambda archive must expose `extractor.py` at the zip root, include the `spotify_data_platform` package, and vendor the runtime dependency needed by that package. The Glue library zip must preserve the `glue/` package hierarchy.

---

## 5. Snowflake Trust Bootstrap

Snowflake storage integrations generate account-specific trust material. For a new environment:

1. create/configure the Snowflake storage integration from a non-versioned deployment copy;
2. obtain the generated `STORAGE_AWS_IAM_USER_ARN` and external ID;
3. provide them locally as `snowflake_iam_user_arn` and `snowflake_external_id`;
4. review the Terraform plan for the AWS trust relationship;
5. configure Snowflake with the Terraform output `snowflake_storage_role_arn` only when performing an explicitly approved deployment.

Real account identifiers and external IDs stay out of version control. `snowflake_external_id` is marked sensitive in Terraform input handling.

---

## 6. Cost Guardrails

Reusable defaults are intentionally conservative for a development portfolio:

- Lambda reserved concurrency: `1`
- Lambda timeout: `30s`
- Glue execution class: `FLEX`
- Glue workers: `2 × G.1X`
- Glue concurrent runs: `1`
- Glue timeout: `15m`
- CloudWatch retention: `7d`
- S3 non-current version retention: `30d`
- AWS Budget: **USD 20/month**
- AWS Budget alerts: **50% actual, 50% forecast, 90% actual, 90% forecast**

The budget email is configurable. AWS Budgets sends alerts; it does not automatically stop workloads or suspend the AWS account.

The bounded v1.0.0 live demo used a separate **manually created USD 5 AWS Budget**. That live guardrail and the Terraform USD 20 reusable default are deliberately documented as different evidence domains.

---

## 7. Offline and CI Validation Contract

Terraform is validated without AWS credentials. The CI path executes:

```bash
terraform fmt -check -recursive infra/terraform

cd infra/terraform
terraform init -backend=false -input=false
terraform validate
tflint --recursive

cd ../..
checkov -d infra/terraform --framework terraform --compact
```

The workflow uses `hashicorp/setup-terraform@v4`, `terraform-linters/setup-tflint@v6`, and Checkov from PyPI. The validation boundary is static/offline: no cloud credentials are injected and no resource mutation occurs.

Checkov remains blocking for unreviewed findings. Explicit skips in the HCL document bounded-development tradeoffs such as:

- no Lambda VPC/NAT path for a public API dependency;
- SSE-S3 instead of customer-managed KMS for non-sensitive portfolio data;
- seven-day operational log retention instead of compliance-archive retention;
- no cross-region S3 replication;
- no second access-log bucket;
- no production-only X-Ray, DLQ, or code-signing controls in the bounded Lambda slice.

Those skips are visible engineering decisions, not blanket security exceptions. They must be revisited before treating this stack as a production/compliance baseline.

---

## 8. Local Configuration

Start from the committed template:

```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars
```

Real `*.tfvars`, state files, `.terraform/`, provider lock files, secret values, and account-specific identifiers are excluded from version control by repository ignore rules.

When `lake_bucket_name` is empty, the root derives:

```text
<project>-<environment>-<aws-account-id>
```

The account ID is used for globally unique naming; it is not embedded in committed configuration.

---

## 9. Deployment Boundary

The reusable operator sequence for a **future Terraform-owned environment** is:

```bash
terraform init
terraform plan
# review the complete plan and ownership boundary
terraform apply
```

Teardown for an environment actually owned by the corresponding Terraform state would be:

```bash
terraform plan -destroy
# review carefully
terraform destroy
```

These commands document the intended lifecycle. They are **not evidence that v1.0.0 applied or destroyed the existing bounded demo environment**. Live ownership should only be claimed after state-backed creation/import and explicit reconciliation of pre-existing resources.
