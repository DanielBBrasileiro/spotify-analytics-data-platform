# Snowflake Data Warehouse Architecture

This directory currently contains only this design README. DDL, RBAC, storage integrations, Snowpipe, and validation queries are planned for M4.

Analytical demonstrations use fully synthetic data under [ADR-0008](../docs/adr/0008-synthetic-analytics-and-source-use-boundary.md).
The responsibilities and directory structure below are targets, not current implementation.

---

## Planned Architectural Responsibility

Snowflake serves as the centralized analytical data warehouse. It provides:
1. **Automated Continuous Ingestion**: Snowpipe listens for Amazon S3 event notifications (via SQS) and loads curated Parquet files directly into Landing tables.
2. **Layered Schemas**:
   - `LANDING`: 1:1 typed representations of S3 Silver Parquet files loaded via Snowpipe (`landing_tracks`, `landing_artists`, `landing_albums`, `landing_track_artists`, `landing_playlist_snapshots`).
   - `STAGING`: Ephemeral or view-based models managed by dbt.
   - `CORE`: Persistent dimensional tables (`dim_*`, `fact_*`, `bridge_*`) managed by dbt.
   - `MARTS`: Curated reporting tables and aggregated views consumed by Power BI.
3. **Audit & Lineage Metadata**:
   - Landing tables capture Snowflake file metadata (`METADATA$FILENAME`, `METADATA$FILE_ROW_NUMBER`, and `_loaded_at`).
   - `spotify_snapshot_id` provides upstream version lineage.
4. **Least-Privilege Security**:
   - Dedicated service roles: `SPOTIFY_LOADER` for Snowpipe write-only access to `LANDING`; `SPOTIFY_TRANSFORMER` for dbt operations; `SPOTIFY_ANALYST` for Power BI read-only access. Privileged roles (`SYSADMIN`, `ACCOUNTADMIN`) are excluded from application runtimes.
5. **Cost-Conscious Virtual Warehouses**:
   - Single `COMPUTE_WH` configured as `X-Small`.
   - Aggressive `AUTO_SUSPEND = 60` seconds.
   - `AUTO_RESUME = TRUE`.

---

## Planned Directory Structure

```
snowflake/
├── ddl/
│   ├── 01_databases_and_schemas.sql     # Database and schema hierarchy
│   ├── 02_rbac_roles_and_grants.sql     # Least privilege RBAC configuration
│   ├── 03_storage_integration.sql       # AWS IAM cross-account storage integration
│   ├── 04_external_stages.sql           # S3 external stage pointing to Silver Parquet
│   ├── 05_file_formats.sql              # Parquet file format specifications
│   ├── 06_landing_tables.sql            # Landing schema table DDL (with track_artists & audit cols)
│   └── 07_snowpipes.sql                 # Snowpipe definitions with auto_ingest = true
└── validation/
    └── verify_landing_loads.sql         # Data integrity and copy history audit queries
```
