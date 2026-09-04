# ADR-0003: Use Apache Parquet for Curated S3 Silver Analytical Datasets

## Status
Accepted

## Context
Raw Spotify API data is landed in S3 Bronze as nested JSON text files. Querying JSON directly or loading raw multi-level JSON into downstream systems exhibits significant performance penalties:
1. High I/O overhead due to uncompressed text representation and repeated JSON keys.
2. Inefficient query scans that read entire documents rather than only the requested columns.
3. High Snowflake ingestion credit consumption when parsing JSON strings in SQL (`PARSE_JSON`).

## Decision
We decide to transform raw Bronze JSON into **Apache Parquet files with Snappy compression in S3 Silver**.

Key technical characteristics:
1. **Columnar Storage**: Optimized for analytical projection and aggregation.
2. **Embedded Metadata & Schemas**: Parquet files encapsulate explicit data types, eliminating ambiguity over timestamps, booleans, and floating-point audio metrics.
3. **Partitioning**: Partitioned by `ingestion_date=YYYY-MM-DD` across curated entity directories:
   - `silver/artists/`
   - `silver/albums/`
   - `silver/tracks/`
   - `silver/track_artists/`
   - `silver/playlist_snapshots/`
4. **Snowpipe Acceleration**: Parquet files are ingested with minimal Snowflake compute compared to unstructured text.

## Alternatives Considered
- **Keep JSON in Silver (Formatted/Cleaned JSON)**:
  - *Pros*: Human-readable text format.
  - *Cons*: 4x-10x larger file sizes, slow Snowflake COPY execution, higher cloud storage costs, lack of column pruning.
- **Delta Lake / Apache Iceberg**:
  - *Pros*: ACID transactions, time travel, and in-place schema evolution on S3.
  - *Cons*: Introduces additional metadata catalogs and engine complexity that exceeds the scope of this pipeline phase. Snowflake natively ingests Parquet via Snowpipe seamlessly.

## Consequences

### Positive Consequences
- **Drastic Storage & Transfer Reduction**: High compression ratio (Snappy on Parquet yields up to 75% size reduction compared to JSON).
- **Fast Warehouse Loading**: Snowflake ingests Parquet with native vectorization and direct column mapping.
- **Cost Reduction**: S3 GET requests, bytes transferred, and Snowflake warehouse active seconds are minimized.

### Negative Consequences
- **Binary Format**: Cannot be inspected with basic terminal tools (`cat`, `less`) without specialized utilities (e.g., `parquet-tools`, DuckDB, or Python).
- **Transformation Overhead**: Requires a distributed compute step (AWS Glue / PySpark) to parse and write Parquet.

## Risks
- Small-file problem if partitions are generated with too many tiny files. Mitigated by coalescing Spark partitions during Glue job execution.

## Review Conditions
Review if multi-table ACID transactions, partition evolution, or in-place table updates on S3 become necessary, which would favor Apache Iceberg.
