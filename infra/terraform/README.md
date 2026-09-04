# Infrastructure as Code (Terraform)

This directory contains Terraform manifests defining and managing the AWS and Snowflake cloud infrastructure.

---

## Architectural Responsibility

- **Declarative Resource Management**: All cloud resources (S3 buckets, IAM roles, Lambda functions, Glue jobs, CloudWatch log groups, and SNS/SQS notification channels) are managed via Terraform.
- **Reproducibility**: Infrastructure can be provisioned on-demand for demonstrations or end-to-end integration testing, and subsequently torn down via `terraform destroy` to enforce zero ongoing cloud spend.
- **Least-Privilege IAM**: IAM policies grant explicit, tightly bounded actions (e.g., Lambda write-only access to S3 Bronze, Glue read Bronze / write Silver).

---

## Planned Directory Structure

```
infra/terraform/
├── main.tf                    # Root orchestration and provider configuration
├── variables.tf               # Environment and configuration variables
├── outputs.tf                 # Resource ARNs, bucket names, and role identifiers
├── terraform.tfvars.example   # Example variable inputs (no secrets)
└── modules/
    ├── s3/                    # Bronze, Silver, and Metadata bucket definitions
    ├── iam/                   # Roles for Lambda, Glue, and Snowflake Storage Integration
    ├── lambda/                # Spotify API extractor function and trigger config
    ├── glue/                  # Glue Spark job definition, script upload, and DPU config
    └── monitoring/            # CloudWatch log groups and metric alarms
```

---

## Cost Governance

- Region pinned to `us-east-1`.
- S3 lifecycle rules configured to transition or expire test snapshots.
- CloudWatch log retention capped at 7 days.
- No NAT Gateways or permanently running EC2 instances.
