# AWS Lambda Extraction Layer

This directory houses the serverless extractor functions responsible for calling the Spotify Web API and landing raw snapshots in Amazon S3.

---

## Architectural Responsibility

- **Short-Lived Execution**: Runs within a serverless container with a timeout bounded to standard API calls (typically < 60 seconds).
- **Authentication**: Fetches client credentials securely from AWS Secrets Manager using IAM least privilege.
- **Immutable Landing**: Ingests complete playlist and track responses without mutating or cleaning data, persisting raw JSON directly to the Bronze layer:
  `s3://<bucket>/bronze/spotify/playlist_tracks/ingestion_date=YYYY-MM-DD/run_id=<run_id>/playlist_<id>.json`
- **Structured Observability**: Emits JSON log events to Amazon CloudWatch containing `pipeline_run_id`, playlist identifiers, response codes, record counts, and elapsed latency.

---

## Planned Directory Structure

```
lambda/
├── src/
│   ├── extractor.py           # Main Lambda handler
│   ├── spotify_client.py      # OAuth2 client and HTTP retry logic
│   └── s3_writer.py           # Multi-part S3 upload utility
├── tests/
│   └── test_extractor.py      # Local Lambda handler unit tests (mocked boto3/requests)
├── requirements.txt           # Runtime dependencies (boto3, requests, etc.)
└── Dockerfile                 # Container image for packaging if dependencies exceed zip limits
```

---

## Cost Optimization

Lambda executes for under a minute per run and is scheduled on a daily cadence, ensuring operational costs remain well within the AWS Free Tier.
