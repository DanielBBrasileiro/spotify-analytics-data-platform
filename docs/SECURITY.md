# Security & Access Governance

Security in v1.0.0 is built around four explicit boundaries: **no committed secrets, prefix-scoped AWS permissions, cross-account trust without static AWS keys, and role-separated Snowflake access**. The reusable Terraform security model is implemented and validated offline/CI, while the bounded live demo environment remains outside Terraform state ownership because no apply/import/destroy lifecycle was executed against it.

> **Visual placeholder — Security trust boundaries and least privilege**
> Target asset: `docs/assets/security/security-trust-boundaries.png`
> Production brief: [`docs/assets/README.md`](assets/README.md), section **Security trust boundaries and least privilege**.

---

## 1. Security Posture at a Glance

| Boundary | v1.0.0 control |
| --- | --- |
| **Secrets** | Spotify credentials live in AWS Secrets Manager or local process environment for `ENVIRONMENT=local`; secret values are not committed |
| **S3** | Private bucket, public access blocked, `BucketOwnerEnforced`, SSE-S3, versioning, non-TLS denied |
| **Lambda** | Write-only to Bronze Spotify objects; read-only access to one configured secret; log-write access only to its own group |
| **Glue** | Read Bronze/artifacts, manage Silver outputs and completion metadata, write only to configured Glue log groups |
| **Snowflake storage integration** | AWS role trusted only by the configured Snowflake IAM user plus `sts:ExternalId`; read-only access to `silver/*` |
| **Snowflake RBAC** | Separate loader, transformer, and analyst roles with different schema/warehouse capabilities |
| **CI** | Static Terraform, SQL, dbt, Spark and orchestration validation without deployment credentials |

The project is a bounded portfolio system, not a compliance-certified production environment. Controls such as customer-managed KMS keys, private networking, long-retention audit archives, code signing, and enterprise identity governance remain explicit extensions rather than hidden assumptions.

---

## 2. Credential and Secret Handling

### Repository boundary

The repository must never contain:

- Spotify client secrets or refresh tokens;
- AWS access keys or session secrets;
- Snowflake passwords, private keys, account locators, generated IAM identities, or storage-integration external IDs;
- production `.env`, `*.tfvars`, Terraform state, PEM/private-key files, or files under credential/secret directories.

Only non-sensitive templates such as `.env.example` and `terraform.tfvars.example` belong in version control. Ignore rules reduce accidental inclusion, but they are not treated as proof that a secret cannot be committed. The repository does not claim a local pre-commit secret scanner as a v1.0.0 control.

### Spotify credential flow

The cloud Lambda runtime reads one existing Secrets Manager object containing:

```json
{
  "client_id": "...",
  "client_secret": "...",
  "refresh_token": "..."
}
```

The runtime validates that document and keeps credential values out of normal object representations and failure telemetry. Terraform receives only the secret **ARN** and does not create or persist the secret payload in state.

For local development, `ENVIRONMENT=local` allows the three Spotify values to come from the process environment. That mode is rejected when the managed Lambda runtime marker is present, preventing a cloud execution from silently falling back to local-style environment credentials.

Credentials and the auth client are cached in a warm process to reduce repeated secret reads. An `invalid_grant` clears the runtime cache so an operator-updated secret can be re-read on a later invocation. A refresh token rotated by Spotify may be used in memory, but v1.0.0 does not write it back to Secrets Manager; granting secret-write capability would require a separate security review.

---

## 3. AWS IAM Least Privilege

The Terraform IAM module defines three separate trust and permission domains. Sensitive workload permissions use explicit actions and resource scopes rather than wildcard allow policies.

### Lambda execution role

Trust principal: `lambda.amazonaws.com`

Allowed runtime actions:

| Capability | Actions | Resource scope |
| --- | --- | --- |
| Publish Bronze snapshot | `s3:PutObject` | `bronze/spotify/*` only |
| Read Spotify credentials | `secretsmanager:GetSecretValue` | Exact configured secret ARN |
| Emit function logs | `logs:CreateLogStream`, `logs:PutLogEvents` | Terraform-created Lambda log group only |

Notably absent: S3 read/delete permission, Secrets Manager write permission, IAM mutation, bucket administration, and `logs:CreateLogGroup`. The log group is provisioned separately by Terraform.

### Glue execution role

Trust principal: `glue.amazonaws.com`

Allowed runtime actions:

| Capability | Actions | Resource scope |
| --- | --- | --- |
| Locate lake | `s3:GetBucketLocation` | Lake bucket |
| Enumerate required areas | `s3:ListBucket` | Prefix-constrained to Bronze, Silver, Glue artifacts, metadata |
| Read inputs/artifacts | `s3:GetObject` | Bronze + `artifacts/glue/*` |
| Curate Silver | `s3:GetObject`, `s3:PutObject`, `s3:DeleteObject`, `s3:AbortMultipartUpload` | `silver/*` |
| Publish completion metadata | `s3:GetObject`, `s3:PutObject` | `metadata/*` |
| Emit Glue logs | `logs:CreateLogStream`, `logs:PutLogEvents` | Configured Glue log groups only |

The delete capability is constrained to Silver because the curation writer may replace run-scoped technical outputs. It does not grant deletion in Bronze, artifacts, or arbitrary bucket prefixes.

### Snowflake storage role

The AWS role used by the Snowflake storage integration has two independent trust requirements:

1. the exact Snowflake-generated AWS IAM user ARN; and
2. the configured `sts:ExternalId`.

Its S3 permissions are read-only:

- `s3:GetBucketLocation` on the lake bucket;
- `s3:ListBucket` only for `silver` / `silver/*`;
- `s3:GetObject` and `s3:GetObjectVersion` only for `silver/*`.

This keeps the warehouse ingestion boundary free of static AWS access keys and prevents Snowflake from writing to or deleting lake data.

### About the `s3:*` deny statement

The S3 module includes `s3:*` only in an explicit **Deny** statement for requests where `aws:SecureTransport = false`. It is a transport-enforcement guardrail, not a wildcard allow permission.

---

## 4. S3 Data Protection

The reusable Terraform bucket enforces:

- all public-access-block controls;
- `BucketOwnerEnforced` ownership;
- server-side encryption with S3-managed AES-256 keys (SSE-S3);
- versioning;
- explicit denial of non-TLS access;
- bounded non-current version retention;
- cleanup of incomplete multipart uploads.

SSE-S3 is a deliberate development/portfolio tradeoff for non-sensitive demo data. v1.0.0 does not claim customer-managed KMS keys, cross-region replication, or a dedicated long-term audit-log bucket. Those controls should be reconsidered for regulated or production-sensitive workloads.

---

## 5. Network and Runtime Boundaries

The optional Spotify Lambda path is intentionally outside a VPC. Its external dependency is the public Spotify API; placing it in private subnets would require NAT or additional endpoint architecture without protecting a private service dependency in this bounded system.

That tradeoff is documented in Terraform static-analysis suppressions rather than hidden. The same approach applies to other bounded-development choices such as no X-Ray, DLQ, or code-signing configuration in the reusable Lambda module.

Cloud/API traffic uses provider HTTPS endpoints, and S3 independently rejects insecure transport. This documentation does not claim an application-enforced TLS minor version for every third-party connection.

---

## 6. Snowflake RBAC

Snowflake service responsibilities are separated by role:

| Role | Warehouse | Data access / responsibility |
| --- | --- | --- |
| `SPOTIFY_LOADER` | **No virtual warehouse usage** required for serverless Snowpipe | LANDING usage, pipe creation, inserts into Landing tables, storage-integration usage |
| `SPOTIFY_TRANSFORMER` | `COMPUTE_WH` usage | Read LANDING; create tables/views in STAGING, CORE and MARTS |
| `SPOTIFY_ANALYST` | `COMPUTE_WH` usage | Read-only access to MARTS tables/views |

The deployment SQL does not assign human users and does not use `ACCOUNTADMIN` or `SYSADMIN` as application runtime roles. Administrative roles are reserved for controlled setup operations such as resource-monitor or identity management.

The storage integration is restricted to the Silver S3 location. `CREATE OR REPLACE STORAGE INTEGRATION` is intentionally avoided because replacing the object can invalidate established trust/stage relationships.

---

## 7. Snowflake Compute Safety

Security and cost controls intersect at the warehouse boundary:

- `COMPUTE_WH` is X-Small, single-cluster, and initially suspended;
- `AUTO_SUSPEND = 60` and `AUTO_RESUME = TRUE` are converged by DDL;
- queued statements time out after 120 seconds;
- statements time out after 900 seconds;
- `SPOTIFY_DEV_MONITOR` has a 2-credit monthly quota;
- the monitor notifies at 80% and uses immediate suspension at 100%.

The resource monitor constrains warehouse compute, not serverless Snowpipe usage or the full Snowflake bill.

---

## 8. Terraform and CI Security Validation

Terraform v1.0.0 is implemented and validated through the repository/CI path with:

```text
terraform fmt
terraform init -backend=false
terraform validate
TFLint
Checkov
```

The CI job does not receive cloud credentials and does not apply infrastructure. Checkov findings are blocking unless the HCL contains an explicit, reviewable skip explaining the bounded-development tradeoff.

Additional offline contracts validate Snowflake DDL structure, Spark transformation behavior, dbt parsing/manifest expectations, and Airflow DAG/service integration. These checks prove repository contracts; they do not substitute for cloud-state ownership or live penetration/security testing.

---

## 9. Live-State Ownership Boundary

The reusable Terraform stack and the bounded v1.0.0 demo must remain separate in security claims.

**What is true:**

- Terraform defines the current S3, IAM, Lambda, Glue, CloudWatch, Snowflake-trust, and AWS Budget desired state.
- That desired state is validated offline/CI.
- The bounded live demo exercised real AWS/Snowflake components under manually controlled guardrails.

**What is not claimed:**

- no Terraform `apply` created the validated live demo environment;
- no import reconciled those live resources into Terraform state;
- no Terraform `destroy` was executed as v1.0.0 evidence;
- therefore Terraform state ownership of the validated live environment is not asserted.

For a future deployment, state ownership should be established deliberately through creation or controlled import/reconciliation before Terraform is treated as the authoritative live control plane.

---

## 10. Security Review Checklist

Before any new live deployment or scope expansion:

- [ ] Confirm no secret value or account-specific trust identifier is committed.
- [ ] Review the Terraform plan for new IAM actions, principals, and resource scopes.
- [ ] Re-check S3 prefix constraints for Lambda, Glue, and Snowflake roles.
- [ ] Confirm the Snowflake external ID and generated IAM user ARN are supplied outside version control.
- [ ] Confirm `SPOTIFY_LOADER`, `SPOTIFY_TRANSFORMER`, and `SPOTIFY_ANALYST` grants still match their intended duties.
- [ ] Review all Checkov suppressions for continued relevance.
- [ ] Reassess whether the workload now requires private networking, customer-managed KMS, longer audit retention, code signing, or stronger organizational controls.
- [ ] Record the live-state ownership boundary before describing resources as Terraform-managed.
