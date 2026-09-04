# References, Inspiration & Attribution

This document records the architectural references, foundational concepts, and official documentation that informed the design of the **Spotify Analytics Data Platform**.

---

## 1. Architectural Inspiration & Originality Statement

The concept of extracting music streaming metadata to build analytical pipelines is a well-established educational paradigm in data engineering.

This platform draws conceptual inspiration from educational Spotify ETL patterns, but **the architectural implementation, infrastructure as code, data models, and codebase are entirely original**:
- **Educational Pattern**: Often consists of a single Python script overwriting daily JSON in S3 and loading flat tables into Snowflake or Athena without testing, versioning, or dimensional modeling.
- **This Platform's Architecture**: Engineered to enterprise standards:
  - Strict separation between Apache Airflow 3.x orchestration and external compute execution.
  - Multi-tiered data lake (Bronze immutable raw JSON -> Silver normalized Parquet).
  - AWS Glue 5.1 (Apache Spark 3.5.6) distributed unnesting of semi-structured items.
  - Automated continuous Snowflake ingestion via Snowpipe with lineage audit metadata.
  - Kimball dimensional star schema (`dim_*`, `fact_*`, `bridge_*`) managed via dbt Core.
  - Historical longitudinal snapshot modeling preserving daily track placement, churn, and retention.
  - Deterministic incremental merge backfills and zero-spend local development workflows.

---

## 2. Official Documentation & Specifications

### Spotify Web API (2026 Specifications)
- [Spotify Developer Platform Documentation](https://developer.spotify.com/documentation/web-api)
- [Spotify Web API: Get Playlist Items Reference (`/v1/playlists/{id}/items`)](https://developer.spotify.com/documentation/web-api/reference/get-playlists-tracks)
- [Spotify Web API: Authorization Code Flow & Scopes](https://developer.spotify.com/documentation/web-api/concepts/authorization)
- [Spotify Web API: Working with Playlists & snapshot_id](https://developer.spotify.com/documentation/web-api/concepts/playlists)
- [Spotify Web API: February 2026 Migration Guide & Changelogs](https://developer.spotify.com/documentation/web-api)

### Apache Spark & AWS Glue
- [AWS Glue 5.1 Release Notes & Runtime Specifications (Spark 3.5.6, Python 3.11)](https://docs.aws.amazon.com/glue/latest/dg/glue-version-5-1.html)
- [Migrating to AWS Glue Version 5.1](https://docs.aws.amazon.com/glue/latest/dg/migrating-to-glue-version-5-1.html)
- [Apache Spark 3.5 Documentation](https://spark.apache.org/docs/3.5.6/)
- [AWS Lambda Pricing & Perpetual Free Tier (400,000 GB-seconds)](https://aws.amazon.com/lambda/pricing/)

### Apache Airflow 3.x
- [Apache Airflow 3.0 Release Notes & Architecture](https://airflow.apache.org/docs/apache-airflow/stable/release_notes.html)
- [Airflow Task SDK Documentation (`airflow.sdk`)](https://airflow.apache.org/docs/task-sdk/stable/)
- [Airflow 3 Deadline Alerts (Replacing Legacy SLAs)](https://airflow.apache.org/docs/apache-airflow/stable/authoring-and-scheduling/deadline-alerts.html)
- [Upgrading from Airflow 2 to Airflow 3](https://airflow.apache.org/docs/apache-airflow/stable/upgrading-to-airflow-3.html)

### Snowflake & Snowpipe
- [Snowflake Continuous Data Pipelines (Snowpipe Auto-Ingest)](https://docs.snowflake.com/en/user-guide/data-load-snowpipe-intro)
- [Snowflake Metadata Columns for Staged Files (`METADATA$FILENAME`, `METADATA$FILE_ROW_NUMBER`)](https://docs.snowflake.com/en/user-guide/querying-metadata)
- [Snowflake External Stages & Storage Integrations for S3](https://docs.snowflake.com/en/user-guide/data-load-s3-config-storage-integration)
- [Snowflake Warehouse Auto-Suspend & Cost Optimization](https://docs.snowflake.com/en/user-guide/cost-understanding-overall)

### dbt Core
- [dbt Core Documentation](https://docs.getdbt.com/docs/build/documentation)
- [dbt-snowflake Adapter Reference](https://docs.getdbt.com/reference/warehouse-setups/snowflake-setup)
- [dbt Incremental Merge Strategy](https://docs.getdbt.com/docs/build/incremental-models)
- [Dimensional Modeling with dbt Best Practices](https://docs.getdbt.com/blog/kimball-dimensional-modeling)

### Infrastructure as Code & Tooling
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [Ruff Linter & Formatter](https://docs.astral.sh/ruff/)
- [pytest Testing Framework](https://docs.pytest.org/en/stable/)
