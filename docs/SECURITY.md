# Security & Access Governance

This document outlines the security architecture, credential management principles, IAM policies, and data protection mechanisms applied across the Spotify Analytics Data Platform.

---

## 1. Zero Credentials in Version Control

This repository adheres to a strict credential exclusion policy:
- No client IDs, client secrets, refresh tokens, access keys, private keys, or passwords may ever be committed to version control.
- The `.gitignore` and `.geminiignore` files explicitly exclude `.env`, `*.pem`, `*.key`, and any files in `credentials/` or `secrets/`.
- Automated pre-commit scans and GitHub secret scanning detect accidental credential inclusions prior to merging.
- Only non-sensitive templates with explicit placeholders (such as `.env.example`) are permitted in version control.

---

## 2. Authentication Architecture & Token Lifecycles

Per **ADR-0007**, the platform implements a decoupled OAuth 2.0 authentication architecture:

```
[Initial Setup]
Operator Consent (Browser) -> Authorization Code Flow -> access_token + refresh_token
                                                                   │
                                                                   ▼
                                                       AWS Secrets Manager
                                                       (Encrypted at rest)
                                                                   │
[Scheduled Run]                                                    │
Airflow / Lambda Extractor ◄───────────────────────────────────────┘
       │
       ▼ (Dynamic Token Exchange)
Spotify Accounts API (grant_type=refresh_token) -> Short-Lived Bearer Token (1 hour)
       │
       ▼ (Playlist Ingestion)
Spotify Web API (/v1/playlists/{id}/items)
```

### Key Security Characteristics:
1. **Interactive Authorization**: Initial authorization and periodic reauthorization are external operator steps using Spotify's Authorization Code Flow with minimal scopes (`playlist-read-private`, `playlist-read-collaborative`).
2. **Cloud Credential Retrieval**: The Issue #7 runtime reads **AWS Secrets Manager** (`spotify/api/credentials`) containing:
   - `client_id`
   - `client_secret`
   - `refresh_token`
   The JSON is validated and secret values are excluded from runtime error messages and object representations.
3. **Local-Only Fallback**: `ENVIRONMENT=local` reads the three Spotify values from process environment. Cloud modes do not fall back to those variables when Secrets Manager fails.
4. **Warm-Container Cache**: Credentials and the `SpotifyAuthClient` instance are cached in process memory, reducing `GetSecretValue` calls and preserving access-token/refresh-token state while the container remains warm. AWS also recommends client-side caching to improve speed and reduce Secrets Manager API cost.
5. **Invalid Grant Recovery Boundary**: `invalid_grant` clears cached credential/auth state. After the operator reauthorizes and updates the secret, a subsequent invocation can retrieve the new value. The runtime never retries the rejected refresh token automatically.
6. **Rotation Limitation**: If Spotify returns a new refresh token during a successful access-token refresh, the warm auth client uses it in memory. Issue #7 does not write that rotated token back to Secrets Manager; adding `PutSecretValue` would require a separate IAM/security review.

---

## 3. Local Development Security

- Developers configure local environments using named AWS CLI profiles (e.g., `AWS_PROFILE=spotify-dev`) using temporary session credentials or AWS SSO rather than long-lived static IAM access keys.
- Local configuration is stored in a non-tracked `.env` file created from `.env.example`.
- The runtime only selects environment credentials when `ENVIRONMENT=local`; test and cloud failures must not silently downgrade to static environment secrets.

---

## 4. IAM Least-Privilege Architecture

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

## 5. Snowflake Access & RBAC Governance

Snowflake access follows Role-Based Access Control (RBAC). Dedicated service roles are used for pipeline automation; privileged accounts (`ACCOUNTADMIN`, `SYSADMIN`) are never used for application runtimes:
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
  - All communications with the Spotify API, AWS APIs, Snowflake, and Power BI use **TLS 1.3** (minimum TLS 1.2).
