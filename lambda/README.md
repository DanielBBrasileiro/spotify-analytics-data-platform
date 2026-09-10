# AWS Lambda Extraction Layer

This directory contains the thin AWS Lambda deployment entrypoint. The tested
runtime implementation lives in `src/spotify_data_platform/lambda_runtime/` so the
same package code is exercised locally and deployed to Lambda.

---

## Architectural Responsibility

- **Validated Invocation Contract**: accepts `playlist_ids`, a UUID v4
  `pipeline_run_id`, and canonical `snapshot_date`; malformed or duplicate playlist
  inputs are rejected before extraction.
- **Credential Provider**: Issue #7 loads `client_id`, `client_secret`, and
  `refresh_token` from AWS Secrets Manager for non-local environments and caches
  them in the Lambda process. `ENVIRONMENT=local` uses explicit process-environment
  credentials without contacting AWS.
- **OAuth 2.0 Token Refresh**: the runtime reuses one `SpotifyAuthClient` per warm
  container, retaining access-token cache and refresh-token rotation in memory.
  `invalid_grant` clears the warm credential/auth cache so a later invocation can
  re-read an operator-updated secret.
- **Get Playlist Items Ingestion**: Calls `GET /v1/playlists/{playlist_id}/items` using pagination (`limit=50`, `offset=0`), capturing upstream `spotify_snapshot_id`.
- **Immutable Landing**: Ingests complete playlist and item responses without mutating or cleaning data, persisting raw JSON directly to the Bronze layer:
  `s3://<bucket>/bronze/spotify/playlist_tracks/ingestion_date=YYYY-MM-DD/run_id=<run_id>/playlist_<id>.json`
- **Conditional S3 Publication**: `PutObject` uses `IfNoneMatch="*"` and explicit
  SSE-S3 (`AES256`). Existing keys return an immutable-collision error instead of
  being overwritten. A transient conditional `409` is retried once.
- **Execution Summary**: successful invocations return HTTP-style status, aggregate
  record counts, per-playlist source versions/S3 URIs, and elapsed milliseconds.
- **Structured Observability**: lifecycle JSON logging is intentionally deferred to
  Issue #8; the current summary is not a replacement for CloudWatch event logs.

---

## Current Directory Structure

```
lambda/
├── src/
│   └── extractor.py           # Thin deployment entrypoint
└── README.md

src/spotify_data_platform/lambda_runtime/
├── credentials.py             # Secrets Manager + local credential provider/cache
├── handler.py                 # Event validation + extraction orchestration
└── s3_writer.py               # Immutable conditional S3 Bronze writer
```

Tests remain under the repository-wide `tests/` tree. They inject HTTP and S3
boundaries, and the default suite blocks outbound sockets. `boto3` is loaded only
when the production S3 client is constructed; AWS Lambda provides an SDK version in
the managed Python runtime. Packaging an explicitly pinned SDK remains a deployment
decision rather than a requirement for offline tests.

The Secrets Manager JSON contract is exactly:

```json
{
  "client_id": "...",
  "client_secret": "...",
  "refresh_token": "..."
}
```

Values are validated without being included in exception messages, model
representations, or Pydantic serialization. Cloud failures do **not** silently fall
back to environment credentials, and `ENVIRONMENT=local` is rejected when the
managed Lambda runtime marker is present. The process cache intentionally trades immediate secret refresh for
fewer API calls; an `invalid_grant` invalidates it. Durable write-back if Spotify
returns a rotated refresh token is not implemented by Issue #7 and would require a
separately reviewed Secrets Manager write permission.

## Verification Boundary

Issues #6/#7 have no live AWS benchmark. The `< 30s` acceptance target must be measured
against monitored playlists after deployment configuration exists. Local tests prove
event validation, real auth/extraction integration through mocked HTTP, canonical S3
keys, conditional upload semantics, cached Secrets Manager retrieval, local fallback,
and sanitized failures without consuming AWS resources or credentials.
