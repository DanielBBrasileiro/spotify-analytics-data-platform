# Security & Access Governance

This document outlines the security architecture, credential management principles, IAM policies, and data protection mechanisms applied across the Spotify Analytics Data Platform.

---

## 1. Zero Secrets Policy

This repository adheres to a strict **Zero Secrets Policy**:
- No client IDs, client secrets, access keys, private keys, or passwords may ever be committed to git.
- The `.gitignore` and `.geminiignore` files explicitly exclude `.env`, `*.pem`, `*.key`, and any files in `credentials/` or `secrets/`.
- Automated pre-commit scans and GitHub secret scanning detect accidental credential inclusions prior to merging.
- Only non-sensitive templates with explicit placeholders (such as `.env.example`) are permitted in version control.

---

## 2. Secrets Management & Credential Injection

### Local Development
- Secrets are stored in a local `.env` file that is strictly ignored by version control.
- Developers instantiate local variables by copying `.env.example` to `.env` and populating local values.

### AWS Cloud Execution
- Spotify API client credentials (`client_id` and `client_secret`) are stored securely in **AWS Secrets Manager** under the secret path `spotify/api/credentials`.
- AWS Lambda fetches credentials dynamically at runtime using the AWS SDK (`boto3`) and caches the token for the duration of the execution context.
- Secrets are never hardcoded into Lambda environment variables or configuration files.

### CI/CD (GitHub Actions)
- Continuous Integration workflows run strictly in dry-run/mock mode and do not require live cloud access.
- If deployment workflows are enabled in future milestones, credentials must be passed via **GitHub Actions Repository Secrets** using OpenID Connect (OIDC) IAM federation.

---

## 3. IAM Least-Privilege Architecture

All AWS execution roles are granted the minimal set of permissions required to perform their discrete function.

### A. AWS Lambda Role (`SpotifyExtractorLambdaRole`)
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "SecretsManagerRead",
      "Effect": "Allow",
      "Action": ["secretsmanager:GetSecretValue"],
      "Resource": "arn:aws:secretsmanager:us-east-1:*:secret:spotify/api/credentials*"
    },
    {
      "Sid": "S3BronzeWrite",
      "Effect": "Allow",
      "Action": ["s3:PutObject"],
      "Resource": "arn:aws:s3:::spotify-analytics-data-platform-*/bronze/spotify/*"
    },
    {
      "Sid": "CloudWatchLogging",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:us-east-1:*:log-group:/aws/lambda/*"
    }
  ]
}
```

### B. AWS Glue Service Role (`SpotifyGlueTransformRole`)
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "S3BronzeRead",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::spotify-analytics-data-platform-*",
        "arn:aws:s3:::spotify-analytics-data-platform-*/bronze/*"
      ]
    },
    {
      "Sid": "S3SilverWrite",
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::spotify-analytics-data-platform-*/silver/*"
    },
    {
      "Sid": "GlueLogging",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:us-east-1:*:log-group:/aws-glue/jobs/*"
    }
  ]
}
```

---

## 4. Snowflake Access & RBAC Governance

Snowflake access follows Role-Based Access Control (RBAC):
- `SECURITYADMIN`: Manages users and role assignments.
- `SYSADMIN`: Manages databases, warehouses, and infrastructure objects.
- `TRANSFORMER_ROLE`: Dedicated service role used by dbt to create and replace models in `STAGING`, `CORE`, and `MARTS`.
- `LOADER_ROLE`: Used by Snowpipe with write permissions strictly to `LANDING`.
- `ANALYST_ROLE`: Read-only role granted access strictly to `MARTS` and consumed by Power BI.

---

## 5. Data Encryption Standards

- **Encryption at Rest**:
  - Amazon S3: Enforced Server-Side Encryption using AWS KMS or S3-Managed Keys (SSE-S3 / AES-256). Unencrypted uploads are denied via bucket policies (`aws:SecureTransport` and `s3:x-amz-server-side-encryption`).
  - Snowflake: Transparent Data Encryption (TDE) protects all internal micro-partitions.
- **Encryption in Transit**:
  - All communications with the Spotify API, AWS APIs, Snowflake, and Power BI use **TLS 1.3** (minimum TLS 1.2).
  - Insecure HTTP traffic is strictly blocked.
