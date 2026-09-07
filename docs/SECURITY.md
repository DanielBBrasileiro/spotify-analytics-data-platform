# Security & Access Governance

This document distinguishes implemented local credential handling from planned cloud security controls. AWS IAM, Secrets Manager persistence, Snowflake RBAC, and cloud encryption settings below are design examples, not deployed controls. Portfolio analytics uses synthetic data under [ADR-0008](adr/0008-synthetic-analytics-and-source-use-boundary.md).

---

## 1. Zero Credentials in Version Control

This repository adheres to a strict credential exclusion policy:
- No client IDs, client secrets, refresh tokens, access keys, private keys, or passwords may ever be committed to version control.
- The `.gitignore` and `.geminiignore` files explicitly exclude `.env`, `*.pem`, `*.key`, and any files in `credentials/` or `secrets/`.
- CI currently checks Ruff and offline tests/coverage. No pre-commit scanner is configured in this repository; GitHub secret-scanning settings have not been verified. Automated scanning remains hardening work.
- Only non-sensitive templates with explicit placeholders (such as `.env.example`) are permitted in version control.

---

## 2. Authentication Architecture & Token Lifecycles

Per [ADR-0007](adr/0007-spotify-authorization-code-and-refresh-token.md),
the local client exchanges an externally supplied refresh token and caches access
tokens in memory. Initial consent and periodic reauthorization are operator steps;
no browser setup utility is implemented in this repository.

| Concern | Current behavior / planned control |
| --- | --- |
| Refresh-token lifetime | Six months from authorization for dashboard apps; access-token refresh does not extend it |
| Access-token lifetime | Use the returned `expires_in` (normally one hour), with a monotonic expiry buffer |
| Rejected grant | `InvalidGrantException`; rejected token cleared and subsequent exchanges blocked |
| Rotation | Current token retained only in memory; future M2 adapter must persist it securely |
| Cloud storage | Planned Secrets Manager secret `spotify/api/credentials`; no adapter deployed |
| Expiry reminders | Planned operator workflow; authorization time cannot be inferred from access-token TTL |

The API restricts playlist items access to the owner or a collaborator. OAuth
consent does not authorize arbitrary downstream analytics. See
[official token lifecycle](https://developer.spotify.com/documentation/web-api/tutorials/refreshing-tokens)
and [items access rules](https://developer.spotify.com/documentation/web-api/reference/get-playlists-items).

For any future permitted real-data use, document retention, disconnection and
deletion before collecting personal data. Normal Bronze append-only processing
must accommodate required deletion; synthetic demos contain no captured user data.

---

## 3. Local Development Security

- Developers configure local environments using named AWS CLI profiles (e.g., `AWS_PROFILE=spotify-dev`) using temporary session credentials or AWS SSO rather than long-lived static IAM access keys.
- Local configuration is stored in a non-tracked `.env` file created from `.env.example`.

---

## 4. IAM Least-Privilege Architecture

The planned AWS roles should grant only permissions required by each component. These illustrative policies are not deployed or integration-tested. The Lambda example covers reading a secret only; secure rotated-token writes require a separately reviewed M2 persistence design and narrowly scoped permissions.

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

## 5. Snowflake Access & RBAC Governance

Planned Snowflake access follows Role-Based Access Control (RBAC). Dedicated service roles are intended for pipeline automation; privileged accounts (`ACCOUNTADMIN`, `SYSADMIN`) are never used for application runtimes:
- `SECURITYADMIN`: Manages user credentials and role hierarchies.
- `SYSADMIN`: Manages warehouses, databases, and resource monitors.
- `SPOTIFY_LOADER`: Used by Snowpipe with write permissions strictly to `LANDING`.
- `SPOTIFY_TRANSFORMER`: Dedicated service role used by dbt to build and merge models across `STAGING`, `CORE`, and `MARTS`.
- `SPOTIFY_ANALYST`: Read-only role granted access strictly to `MARTS` and consumed by Power BI.

---

## 6. Data Encryption Standards

- **Encryption at Rest**:
  - Amazon S3: Enforced Server-Side Encryption using S3-Managed Keys (SSE-S3 / AES-256) or AWS KMS.
  - Snowflake: Transparent Data Encryption (TDE) protects all micro-partitions.
- **Encryption in Transit**:
  - The local HTTP transport verifies TLS certificates; no negotiated TLS version was measured. Future integrations should require provider-supported secure TLS (minimum 1.2), with negotiated versions validated during integration testing.
