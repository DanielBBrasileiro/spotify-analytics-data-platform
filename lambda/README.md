# AWS Lambda Extraction Layer

This directory houses the serverless extractor functions responsible for calling the Spotify Web API and landing raw snapshots in Amazon S3.

---

## Architectural Responsibility

- **Short-Lived Execution**: Runs within a serverless container with a timeout bounded to standard API calls (typically < 30 seconds).
- **OAuth 2.0 Token Refresh**: Dynamically retrieves `client_id`, `client_secret`, and `refresh_token` from AWS Secrets Manager (`spotify/api/credentials`), exchanges the refresh token with Spotify Accounts for a short-lived access token (valid for 1 hour), and caches the token in runtime memory (ADR-0007).
- **Get Playlist Items Ingestion**: Calls `GET /v1/playlists/{playlist_id}/items` using pagination (`limit=50`, `offset=0`), capturing upstream `spotify_snapshot_id`.
- **Immutable Landing**: Ingests complete playlist and item responses without mutating or cleaning data, persisting raw JSON directly to the Bronze layer:
  `s3://<bucket>/bronze/spotify/playlist_tracks/ingestion_date=YYYY-MM-DD/run_id=<run_id>/playlist_<id>.json`
- **Structured Observability**: Emits JSON log events to Amazon CloudWatch containing `pipeline_run_id`, `spotify_snapshot_id`, playlist identifiers, response codes, record counts, and elapsed latency.

---

## Planned Directory Structure

```
lambda/
├── src/
│   ├── extractor.py           # Main Lambda handler
│   ├── spotify_auth.py        # Token exchange and in-memory caching logic
│   ├── spotify_client.py      # HTTP client, pagination, and retry logic
│   ├── s3_writer.py           # S3 Bronze upload utility
│   └── logger.py              # Structured JSON logging formatter
├── tests/
│   └── test_extractor.py      # Local Lambda handler unit tests (mocked boto3/requests)
├── requirements.txt           # Runtime dependencies (boto3, requests, etc.)
└── Dockerfile                 # Container image for packaging if dependencies exceed zip limits
```

---

## Cost Optimization

Lambda executes for under 30 seconds per run and is scheduled on a daily cadence, consuming < 8 GB-seconds per day, which falls well within the AWS Lambda perpetual free tier (400,000 GB-seconds and 1M requests per month).
