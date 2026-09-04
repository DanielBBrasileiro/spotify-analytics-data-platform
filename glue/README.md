# AWS Glue / Apache Spark Processing Layer

This directory contains the PySpark scripts and transformation jobs executed on AWS Glue.

---

## Architectural Responsibility

Per **ADR-0005**, AWS Glue / Apache Spark handles technical extraction, schema enforcement, unnesting, deduplication, and Parquet serialization from S3 Bronze to S3 Silver. It does **not** perform business dimensional modeling (which is reserved for dbt in Snowflake).

### Core Responsibilities:
1. **Semi-Structured Parsing**: Ingest raw, deeply nested Spotify API JSON payloads from S3 Bronze.
2. **Strict Schema Enforcement**: Apply explicit PySpark StructTypes to prevent schema drift and silent type coercion.
3. **Array Explosion & Normalization**: Explode nested arrays (`tracks.items`, `track.artists`, etc.) into relational tabular representations:
   - `artists` (artist metadata, genres, popularity)
   - `albums` (album metadata, release date, track count)
   - `tracks` (track metadata, duration, explicit flag, popularity)
   - `track_artists` (bridge relation resolving many-to-many track/artist mappings)
   - `playlist_snapshots` (point-in-time state of playlist tracks)
4. **Technical Deduplication**: Deduplicate entities across runs using entity IDs.
5. **Columnar Parquet Output**: Write snappy-compressed Parquet datasets to S3 Silver partitioned by `ingestion_date=YYYY-MM-DD`.

---

## Planned Directory Structure

```
glue/
├── jobs/
│   └── bronze_to_silver_curation.py     # Main PySpark Glue ETL script
├── schemas/
│   ├── bronze_schema.py                 # PySpark StructType definitions for Bronze JSON
│   └── silver_schemas.py                # Target schemas for Silver Parquet entities
├── tests/
│   └── test_bronze_to_silver.py         # PySpark unit tests (run locally via local Spark)
└── config/
    └── job_parameters.json              # Glue job arguments and Spark configurations
```

---

## Local Development vs Cloud Execution

- Unit tests and schema validations will be executed locally using pytest and a local PySpark session.
- Cloud Glue jobs will be triggered on-demand by Airflow or during integration tests using minimal Data Processing Units (e.g., 2 DPUs, Glue 4.0).
