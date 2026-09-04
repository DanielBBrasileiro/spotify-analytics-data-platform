# ADR-0005: Separate Technical Spark Transformations from Analytical dbt Models

## Status
Accepted

## Context
A recurring architectural question in modern data platforms is whether to execute all data transformations in Apache Spark (e.g., AWS Glue, EMR, Databricks) or entirely within the cloud data warehouse using dbt.

Running both Spark and dbt can appear redundant if their responsibilities are not strictly separated. Conversely, forcing either tool to handle the entire lifecycle introduces severe inefficiencies:
- **Transforming raw nested JSON entirely in Snowflake**: Incurs high warehouse compute costs executing recursive `FLATTEN`, `LATERAL FLATTEN`, and `PARSE_JSON` expressions on raw uncompressed text.
- **Performing dimensional modeling and business marts entirely in Spark**: Requires reinventing SQL testing frameworks, schema documentation, lineage graphs, incremental merge logic, and semantic layer integrations that dbt provides out of the box.

## Decision
We decide to establish a **strict division of responsibilities** between **AWS Glue / Apache Spark** (Data Lake tier) and **dbt Core** (Data Warehouse tier).

```
Raw JSON (Bronze S3)
       │
       ▼ [AWS Glue / PySpark] -> Technical ETL & Serialization
Curated Parquet (Silver S3)
       │
       ▼ [Snowpipe] -> Automated Ingestion
Landing Tables (Snowflake)
       │
       ▼ [dbt Core] -> Dimensional Modeling & Business Logic
Core & Marts (Snowflake)
```

### AWS Glue / PySpark Responsibilities (Data Lake Tier):
1. **Semi-Structured Ingestion**: Ingest high-volume raw JSON objects from S3 Bronze.
2. **Explicit Schema Enforcement**: Validate structural integrity via PySpark `StructType` definitions to isolate schema drift at the ingestion boundary.
3. **Complex Nested Array Explosion**: Efficiently unnest deeply nested arrays (`tracks.items`, `artists`, `available_markets`) using Spark distributed memory.
4. **Relational Extraction**: Normalize single JSON documents into discrete tabular entity datasets (`artists`, `albums`, `tracks`, `track_artists`, `playlist_snapshots`).
5. **Technical Deduplication**: Deduplicate identical payload records within the ingestion batch.
6. **Optimized Storage Serialization**: Write partitioned, Snappy-compressed Parquet datasets to S3 Silver.

### dbt Core Responsibilities (Data Warehouse Tier):
1. **Staging & Casting**: Clean column naming conventions, enforce typing, and document upstream sources (`stg_spotify_*`).
2. **Dimensional Modeling**: Build Kimball star schema models (`dim_track`, `dim_artist`, `dim_album`, `dim_playlist`, `bridge_track_artist`, `fact_playlist_snapshot`).
3. **Surrogate Key Management**: Generate deterministic surrogate hashes (`dbt_utils.generate_surrogate_key`).
4. **Business Metrics & Marts**: Construct aggregated reporting tables (`mart_artist_performance`, `mart_playlist_trends`, `mart_playlist_changes`).
5. **Analytical Quality Gates**: Execute schema and data tests (`unique`, `not_null`, `relationships`, domain assertions).
6. **Lineage & Catalog**: Generate searchable data dictionaries and DAG lineage documentation.

## Why Both Exist (Why This Is Not Redundant)

| Dimension | AWS Glue / PySpark | dbt Core on Snowflake |
| :--- | :--- | :--- |
| **Primary Domain** | Data Lake / Storage Optimization | Data Warehouse / Analytics Engineering |
| **Compute Paradigm** | Distributed Spark JVM Memory | Massively Parallel SQL Engine (Snowflake) |
| **Input Format** | Raw semi-structured JSON | Clean columnar relational tables |
| **Output Format** | Compressed, partitioned Parquet | Materialized tables / views in Snowflake |
| **Strength** | Heavy unnesting, binary serialization, low-cost processing | Semantic modeling, SQL modularity, automated testing, documentation |
| **Cost Profile** | Pay-per-DPU-second (Glue) | Pay-per-second warehouse credits |

Separating these tiers ensures that the data warehouse never pays premium SQL credits to unpack raw JSON strings, while analytics engineers never have to write complex PySpark code to maintain business metrics and star schemas.

## Alternatives Considered
- **All-in-Snowflake (ELT via SQL)**: Ingest raw JSON directly into Snowflake variant columns and flatten with dbt. Rejected due to high credit consumption during JSON parsing and loss of an open, queryable S3 Silver lake.
- **All-in-PySpark (ETL via Spark)**: Use PySpark to write dimensional tables directly into warehouse JDBC tables or Delta Lake. Rejected due to the lack of native dbt testing, automated lineage, and modular SQL composability.

## Consequences

### Positive Consequences
- **Cost Efficiency**: JSON unnesting happens on cost-effective Glue DPUs; Snowflake only queries pre-flattened, optimized Parquet.
- **Role Alignment**: Data engineers handle pipeline ingestion and storage formats; analytics engineers operate natively in SQL.
- **Auditability**: S3 Silver remains an open, cloud-agnostic Parquet asset that can be queried by Athena, DuckDB, or alternative query engines.

### Negative Consequences
- **Two Development Runtimes**: Engineers must maintain both PySpark code (and tests) and dbt SQL models.
- **Pipeline Handoff**: Orchestrator must bridge the transition from Glue completion to Snowpipe ingestion and dbt execution.

## Risks
- Data contract mismatch between Glue Parquet column names and dbt source definitions. Mitigated by explicit schema definitions in code and automated CI tests.

## Review Conditions
Review if Snowflake introduces zero-cost JSON parsing optimizations that eliminate Spark's cost advantage, or if Apache Iceberg unifies both tiers under a single engine.
