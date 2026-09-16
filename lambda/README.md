# AWS Lambda Extraction Layer

This directory contains the thin AWS Lambda deployment entrypoint. The tested
runtime implementation lives in `src/spotify_data_platform/lambda_runtime/` so the
same package code is exercised locally and deployed to Lambda.

---

## Architectural Responsibility

- **Validated Invocation Contract**: accepts `playlist_ids`, a UUID v4
  `pipeline_run_id`, and canonical `snapshot_date`; malformed or duplicate playlist
  inputs are rejected before extraction.
- **Credential Provider**: loads `client_id`, `client_secret`, and
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
- **Structured Observability**: emits compact JSON lifecycle events for
  extraction start, each version-checked page, successful S3 publication, completion,
  and sanitized failures. `spotify_snapshot_id` is `null` until the source version is
  known; exception messages and raw payloads are never included in failure telemetry.

---

## Current Directory Structure

```
lambda/
├── src/
│   ├── extractor.py           # Thin deployment entrypoint
│   └── logger.py              # Deployment exports for JSON telemetry
└── README.md

src/spotify_data_platform/lambda_runtime/
├── credentials.py             # Secrets Manager + local credential provider/cache
├── handler.py                 # Event validation + extraction orchestration
├── s3_writer.py               # Immutable conditional S3 Bronze writer
└── telemetry.py               # JSON formatter + lifecycle telemetry logger
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
returns a rotated refresh token is not implemented and would require a
separately reviewed Secrets Manager write permission.

## Telemetry Contract

The runtime emits the following event names:

| Event | Meaning |
| --- | --- |
| `EXTRACTION_START` | Playlist processing started; `spotify_snapshot_id` may still be `null`. |
| `PAGINATION_PAGE_FETCHED` | One page passed pagination and source-version validation. |
| `S3_WRITE_SUCCESS` | The immutable Bronze object was conditionally published. |
| `EXTRACTION_COMPLETE` | One playlist completed successfully. |
| `EXTRACTION_FAILED` | Playlist processing failed; only `error_type` is recorded, never exception text. |

Every structured event contains `timestamp`, `event`, `level`, `source`, `component`,
`pipeline_version`, `pipeline_run_id`, `playlist_id`, `spotify_snapshot_id`,
`snapshot_date`, `duration_ms`, and `status`. The dedicated logger owns exactly one
JSON stream handler across warm invocations. Unexpected unstructured messages have
their free-form text suppressed instead of being copied into telemetry.

When deployed in managed Lambda, these standard logging streams are captured by CloudWatch
Logs. The Terraform monitoring module defines the function log group with a seven-day
retention policy for the reusable development shape. v1.0.0 does **not** claim that a live
Spotify Lambda invocation was part of the bounded cloud demo, and it does not claim a managed
CloudWatch metric/alarm dashboard around this source path.

## Verification Boundary

The source-side Lambda path has no v1.0.0 live Spotify benchmark. Any latency target must be
measured against an explicitly authorized live playlist before it is presented as evidence.
Automated tests prove
event validation, real auth/extraction integration through mocked HTTP, canonical S3
keys, conditional upload semantics, cached Secrets Manager retrieval, local fallback,
page-level telemetry, single-line JSON formatting, warm logger idempotency, and
sanitized failures without consuming AWS resources or credentials.

The public bounded portfolio demo intentionally begins from the CC0-backed source adapter and
joins this architecture at the same Bronze contract. See
[`../docs/LOCAL_INGESTION.md`](../docs/LOCAL_INGESTION.md) for the source boundary and
[`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md) for the validated path.
