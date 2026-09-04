# Snowflake Data Warehouse Architecture

This directory contains Snowflake DDL scripts, RBAC definitions, storage integrations, and Snowpipe configurations.

---

## Architectural Responsibility

Snowflake serves as the centralized analytical data warehouse. It provides:
1. **Automated Continuous Ingestion**: Snowpipe listens for Amazon S3 event notifications (via SQS) and loads curated Parquet files directly into Landing tables.
2. **Layered Schemas**:
   - `LANDING`: Raw, 1:1 representations of S3 Silver Parquet files loaded via Snowpipe (`landing_tracks`, `landing_artists`, `landing_albums`, `landing_playlist_snapshots`).
   - `STAGING`: Ephemeral or view-based models managed by dbt.
   - `CORE`: Persistent dimensional tables (`dim_*`, `fact_*`, `bridge_*`) managed by dbt.
   - `MARTS`: Curated reporting tables and aggregated views consumed by Power BI.
3. **Cost-Conscious Virtual Warehouses**:
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
│   ├── 06_landing_tables.sql            # Landing schema table DDL
│   └── 07_snowpipes.sql                 # Snowpipe definitions with auto_ingest = true
└── validation/
    └── verify_landing_loads.sql         # Data integrity and copy history audit queries
```
