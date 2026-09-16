# AWS infrastructure (Terraform)

This Terraform root defines the low-cost AWS development shape for the Spotify analytics data platform: one private S3 lake, one Python 3.12 Lambda extractor, one Glue 5.1 Spark job, least-privilege IAM roles, bounded CloudWatch retention, and a monthly AWS Budget.

## Resources

- One S3 bucket with `bronze/`, `silver/`, `artifacts/`, and `metadata/` prefixes. It is private, uses SSE-S3 encryption, has versioning enabled, denies non-TLS requests, aborts incomplete multipart uploads after seven days, and expires non-current object versions after 30 days.
- One Lambda Python 3.12 function with reserved concurrency `1`. Its role can write only `bronze/spotify/*`, read only the configured Spotify Secrets Manager secret, and write only its own CloudWatch log streams.
- One Glue 5.1 Spark job using `FLEX`, two `G.1X` workers by default, a single concurrent run, and a 15-minute timeout. Its role reads Bronze and Glue artifacts and can write/delete only Silver outputs and completion metadata.
- One Snowflake storage role trusted only by the configured Snowflake IAM user plus `sts:ExternalId`, with read-only access to `silver/*`.
- Lambda and standard Glue job log groups with seven-day retention.
- One monthly AWS Budget, `$20` by default, with email notifications for both actual and forecast spend at 50% and 90%.

The stack deliberately avoids NAT Gateways, EC2, databases, customer-managed KMS keys, and always-on compute.
AWS Budgets only sends threshold notifications; it does not automatically stop workloads or suspend the account.
Taggable resources inherit `Project = SpotifyAnalyticsDataPlatform`, `Environment = dev`, and `ManagedBy = Terraform` by default.

## Runtime artifacts

Terraform provisions the runtime resources but does not build Python packages. Before an apply, place these objects in the lake bucket (or override their keys):

```text
artifacts/lambda/spotify-ingestion.zip
artifacts/glue/bronze_to_silver_curation.py
artifacts/glue/spotify-glue-lib.zip
```

The Lambda archive must expose `extractor.py` at the zip root, include the `spotify_data_platform` package, and vendor its runtime dependency (`pydantic`). The Glue library zip must preserve the `glue/` package path so imports such as `glue.schemas` and `glue.transforms` resolve.

The Spotify secret is intentionally external to Terraform state. Its JSON value contains `client_id`, `client_secret`, and `refresh_token`; Terraform receives only its ARN.

## Snowflake trust bootstrap

Snowflake exposes the IAM user ARN and external ID used by an AWS storage integration. Supply those locally as `snowflake_iam_user_arn` and `snowflake_external_id`. Terraform builds the constrained trust policy and outputs `snowflake_storage_role_arn`, which is the role ARN configured in Snowflake.

## Local configuration

```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars
```

Real `*.tfvars`, state, `.terraform/`, and provider lock files are ignored by git. Keep the Snowflake external ID and every secret value out of committed files.

When `lake_bucket_name` is empty, Terraform derives `<project>-<environment>-<aws-account-id>`.

## Offline validation

CI runs the same checks without AWS credentials:

```bash
terraform fmt -check -recursive
terraform init -backend=false -input=false
terraform validate
tflint --recursive
checkov -d . --framework terraform --compact
```

`terraform plan` and `terraform apply` require AWS credentials and valid local variables. CI never applies cloud resources.

Checkov remains blocking for unreviewed findings. The HCL contains explicit, reasoned skips for
controls that intentionally conflict with this bounded low-cost development architecture, such
as a Lambda VPC/NAT path, customer-managed KMS keys, one-year log retention, cross-region S3
replication, a second access-log bucket, and production-only tracing/code-signing controls.
Those skips are visible in code and should be revisited before treating this stack as a
production/compliance baseline.

## Cost guardrails

Defaults are intentionally bounded for a portfolio/dev environment: Lambda concurrency `1`, Glue `FLEX` with two `G.1X` workers, 15-minute Glue timeout, seven-day CloudWatch retention, 30-day non-current S3 version retention, and a `$20/month` budget with actual plus forecast notifications at 50% and 90%.
The development lake defaults to `force_destroy = true` so a deliberate `terraform destroy` can remove versioned data and staged runtime artifacts instead of leaving billable S3 objects behind.
