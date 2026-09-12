# AWS Glue 5.1 / Apache Spark Processing Layer

This directory contains the PySpark scripts and transformation jobs executed on AWS Glue.

---

## Architectural Responsibility

Per **ADR-0005**, AWS Glue 5.1 (Apache Spark 3.5.6 / Python 3.11) handles technical extraction, schema enforcement, item validation, deduplication, and Parquet serialization from S3 Bronze to S3 Silver. It does **not** perform business dimensional modeling (which is reserved for dbt in Snowflake).

### Core Responsibilities:
1. **Semi-Structured Parsing**: Ingest raw, deeply nested Spotify API JSON payloads from S3 Bronze.
2. **Strict Schema Enforcement**: Apply explicit PySpark `StructType` definitions to prevent schema drift and silent type coercion.
3. **Item Validation & Array Explosion**:
   - Inspect `item` structures: validate track items and route non-track items (e.g., episodes) to quarantine.
   - Explode nested arrays (`track.artists`, album metadata) into relational tabular representations:
     - `artists` (artist metadata)
     - `albums` (album metadata, release date, track count)
     - `tracks` (track metadata, duration, explicit flag)
     - `track_artists` (bridge relation resolving many-to-many track/artist mappings)
     - `playlist_snapshots` (point-in-time state of playlist slots preserving `spotify_snapshot_id`)
4. **Technical Deduplication**: Deduplicate entities across runs using entity IDs.
5. **Columnar Parquet Output**: Write snappy-compressed Parquet datasets to S3 Silver partitioned by `ingestion_date=YYYY-MM-DD`.

---

## Current Directory Structure

```
glue/
├── jobs/
│   └── bronze_to_silver_curation.py     # Main PySpark Glue 5.1 ETL script
├── schemas/
│   ├── bronze_schema.py                 # PySpark StructType definitions for Bronze JSON
│   ├── silver_schemas.py                # Target schemas for Silver Parquet entities
│   └── validation.py                    # Structural/required-value contract checks
├── storage/
│   └── layout.py                        # Canonical Silver partition paths
└── transforms/
    ├── entities.py                      # Artists/albums/tracks/bridge normalization
    ├── snapshots.py                     # Historical playlist-slot normalization
    ├── dedup.py                         # Deterministic technical deduplication
    └── quarantine.py                    # Sanitized rejected-item classification
```

The canonical output contract is deliberately identical for local development and S3:

```text
silver/<dataset>/ingestion_date=YYYY-MM-DD/
```

Supported datasets are `artists`, `albums`, `tracks`, `track_artists`, and
`playlist_snapshots`. The `ingestion_date` column is also retained inside each Parquet
file because the Snowflake Landing contract exposes it as a normal column as well as an
S3 partition value.

---

## Local Development vs Cloud Execution

- Unit tests and schema validations are executed locally using pytest and a local PySpark 3.5.6 session.
- Cloud Glue jobs will be triggered on-demand by Airflow or during integration tests using minimal Data Processing Units (e.g., 2 DPUs, Glue 5.1).
