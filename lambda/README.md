# AWS Lambda Extraction Layer

This directory currently contains only this design README. The handler, S3 writer, secret-store adapter, and structured logging are planned for M2. Existing auth and extraction code lives in `src/spotify_data_platform/` and should be reused.

Analytical demonstrations use fully synthetic data under [ADR-0008](../docs/adr/0008-synthetic-analytics-and-source-use-boundary.md).
The responsibilities and directory structure below are targets, not current implementation.

---

## Planned Architectural Responsibility

- **Bounded Execution**: Define a total execution budget when building the adapter. Current HTTP timeouts apply per socket operation; pagination and Retry-After can extend a run. No sub-30-second duration has been measured.
- **OAuth 2.0 Token Refresh**: Dynamically retrieves `client_id`, `client_secret`, and `refresh_token` from AWS Secrets Manager (`spotify/api/credentials`), exchanges the refresh token with Spotify Accounts for a short-lived access token (valid for 1 hour), and caches the token in runtime memory (ADR-0007).
- **Get Playlist Items Ingestion**: Calls `GET /v1/playlists/{playlist_id}/items` using pagination (`limit=50`, `offset=0`), reading `snapshot_id` from playlist metadata before pagination and after each page. Items pages do not include it; observed changes raise `SnapshotChangedException`.
- **Immutable Landing**: Ingests complete playlist and item responses without mutating or cleaning data, persisting raw JSON directly to the Bronze layer:
  `s3://<bucket>/bronze/spotify/playlist_tracks/ingestion_date=YYYY-MM-DD/run_id=<run_id>/playlist_<id>.json`
- **Structured Observability**: Emits JSON log events to Amazon CloudWatch containing `pipeline_run_id`, `spotify_snapshot_id`, playlist identifiers, response codes, record counts, and elapsed latency.

---

## Planned Directory Structure

```
lambda/
├── src/
│   ├── extractor.py           # Main Lambda handler
│   ├── s3_writer.py           # S3 Bronze upload utility
│   └── logger.py              # Structured JSON logging formatter
├── tests/
│   └── test_extractor.py      # Local Lambda handler unit tests (mocked boto3/requests)
├── requirements.txt           # Adapter dependencies selected during M2; reuse existing client
└── Dockerfile                 # Container image for packaging if dependencies exceed zip limits
```

---

## Cost Optimization

Measure duration, memory, retries, and invocations when the adapter exists.
Free Tier eligibility and remaining allowances depend on the account and current
terms; no zero-cost or fixed-duration claim is validated. See
[Cost Strategy](../docs/COST_STRATEGY.md).

The future secret-store adapter must persist rotated tokens securely and provide
an operator reauthorization path after six-month expiry or revocation. The
existing client handles rotation only in memory.
