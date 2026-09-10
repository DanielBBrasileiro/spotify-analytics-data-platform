# Infrastructure as Code (Terraform)

This directory currently contains only this design README. No `.tf` manifests, state, or deployed resources are established here; infrastructure implementation is planned for M8.

Analytical demonstrations use fully synthetic data under [ADR-0008](../../docs/adr/0008-synthetic-analytics-and-source-use-boundary.md).
The responsibilities and directory structure below are targets, not current implementation.

---

## Planned Architectural Responsibility

- **Declarative Resource Management**: Future cloud resources (S3, IAM, Lambda, Glue, logging, and notification channels) should be defined through Terraform before deployment.
- **Reproducibility**: Infrastructure can be provisioned on-demand for demonstrations or end-to-end integration testing, and subsequently torn down via `terraform destroy` to reduce ongoing charges. Teardown completion and residual storage/serverless costs must be verified; destruction is not an instantaneous billing guarantee.
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
