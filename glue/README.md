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
5. **Columnar Parquet Output**: Write snappy-compressed Parquet datasets to collision-free S3 Silver prefixes scoped by `ingestion_date`, physical `run_id`, and `playlist_id`.

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
silver/<dataset>/ingestion_date=YYYY-MM-DD/run_id=<uuid>/playlist_id=<id>/
```

Supported datasets are `artists`, `albums`, `tracks`, `track_artists`, and
`playlist_snapshots`. The `ingestion_date` column is also retained inside each Parquet
file because the Snowflake Landing contract exposes it as a normal column as well as an
S3 partition value.

---

## Local Development vs Cloud Execution

- Unit tests and schema validations are executed locally using pytest and a local PySpark 3.5.6 session.
- The repository's primary Python package remains on Python 3.12+, while the `glue/` test
  environment intentionally mirrors AWS Glue 5.1 with **Python 3.11 + Java 17 +
  PySpark 3.5.6**. PySpark is therefore not a normal application dependency.
- Create the isolated local environment with a Python 3.11 interpreter, then install:

  ```bash
  python3.11 -m venv .venv-spark
  .venv-spark/bin/pip install -r glue/requirements-dev.txt
  ```

  When using pyenv, an equivalent explicit command is:

  ```bash
  PYENV_VERSION=3.11.9 python -m venv .venv-spark
  ```

- Point `JAVA_HOME` to a Java 17 installation and run `make spark-test`. On an Apple
  Silicon Homebrew setup, one valid example is:

  ```bash
  export JAVA_HOME=/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home
  make spark-test
  ```

- The default Python 3.12 CI suite keeps its five-second budget and does not start a JVM.
  A separate CI job mirrors Glue 5.1 and runs only `tests/spark` with external network
  access blocked while allowing Py4J loopback sockets.
- Cloud Glue execution remains intentionally deferred. No AWS API call or Glue DPU is
  required to validate M3 locally.
