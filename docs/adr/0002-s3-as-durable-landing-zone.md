# ADR-0002: Use Amazon S3 Bronze as Durable, Immutable Landing Layer

## Status
Accepted

## Context
Ingesting data directly from the Spotify Web API into an operational database or data warehouse without preserving raw payloads creates data loss risks:
1. Upstream Spotify API schema changes or new nested fields cannot be retroactively recovered if only flattened fields are stored.
2. If downstream transformation logic contains bugs, historical pipeline runs cannot be reprocessed or audited.
3. Overwriting yesterday's extraction destroys historical playlist composition and track positioning.

## Decision
We decide to land all extracted Spotify API responses as **immutable, raw JSON objects in Amazon S3 Bronze** prior to any schema normalization, filtering, or deduplication.

Target path format:
`s3://<bucket>/bronze/spotify/playlist_tracks/ingestion_date=YYYY-MM-DD/run_id=<pipeline_run_id>/playlist_<id>.json`

Key architectural rules:
1. **Immutability**: Once written, raw objects are never overwritten or mutated in place.
2. **Deterministic Partitioning**: Partitioned by `ingestion_date=YYYY-MM-DD` and scoped by a unique `run_id`.
3. **Replayability**: Downstream silver and gold layers can be dropped and rebuilt entirely from Bronze objects.

## Alternatives Considered
- **Direct-to-Warehouse Ingestion (Lambda to Snowflake Landing)**:
  - *Pros*: Eliminates S3 intermediate storage and Glue ETL step.
  - *Cons*: Couples extraction directly to Snowflake compute costs, loses cloud-agnostic data lake durability, and incurs warehouse compute charges for raw ingestion parsing.
- **Overwriting Current-State JSON (`s3://.../latest/playlist.json`)**:
  - *Pros*: Minimal storage usage.
  - *Cons*: Destroys snapshot history, prevents trend analysis, and violates auditability requirements.

## Consequences

### Positive Consequences
- **Complete Replayability**: Any pipeline logic defect in Spark or dbt can be resolved by backfilling from Bronze without re-querying the rate-limited Spotify API.
- **Auditability**: Provides an exact cryptographic and temporal record of upstream API payloads.
- **Decoupled Extraction & Transformation**: Lambda can finish its extraction quickly and land data without waiting for warehouse or Spark availability.

### Negative Consequences
- **Storage Accumulation**: Raw JSON accumulates daily and requires automated lifecycle management (e.g., transition to S3 Standard-IA or Glacier, or deletion after a retention horizon in non-production environments).
- **Two-Phase Ingestion**: Ingestion requires both landing in S3 and subsequent processing into Silver/Snowflake.

## Risks
- Storage costs if retention policies are omitted. Mitigated via Terraform S3 lifecycle rules.
- Potential schema drift in raw JSON if Spotify modifies undocumented endpoint responses. Mitigated by storing unmodified source JSON in Bronze.

## Review Conditions
Review if source data scale exceeds millions of objects per day, necessitating direct streaming ingestion into an open table format (e.g., Apache Iceberg) rather than discrete JSON files.
