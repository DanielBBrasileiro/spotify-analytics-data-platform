# AWS Lambda Extraction Layer

This directory contains the thin AWS Lambda deployment entrypoint. The tested
runtime implementation lives in `src/spotify_data_platform/lambda_runtime/` so the
same package code is exercised locally and deployed to Lambda.

---

## Architectural Responsibility

- **Validated Invocation Contract**: accepts `playlist_ids`, a UUID v4
  `pipeline_run_id`, and canonical `snapshot_date`; malformed or duplicate playlist
  inputs are rejected before extraction.
- **OAuth 2.0 Token Refresh**: Issue #6 reuses the existing `SpotifyAuthClient` and
  currently obtains credentials from the process environment. AWS Secrets Manager
  retrieval and warm-container credential caching are Issue #7.
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
├── handler.py                 # Event validation + extraction orchestration
└── s3_writer.py               # Immutable conditional S3 Bronze writer
```

Tests remain under the repository-wide `tests/` tree. They inject HTTP and S3
boundaries, and the default suite blocks outbound sockets. `boto3` is loaded only
when the production S3 client is constructed; AWS Lambda provides an SDK version in
the managed Python runtime. Packaging an explicitly pinned SDK remains a deployment
decision rather than a requirement for offline tests.

## Verification Boundary

Issue #6 has no live AWS benchmark. The `< 30s` acceptance target must be measured
against monitored playlists after deployment configuration exists. Local tests prove
event validation, real auth/extraction integration through mocked HTTP, canonical S3
keys, conditional upload semantics, and sanitized failures without consuming AWS
resources or credentials.
