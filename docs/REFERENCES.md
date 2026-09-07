# References, Inspiration & Attribution

This document records the architectural references, foundational concepts, and official documentation that informed the design of the **Spotify Analytics Data Platform**.

---

## 1. Architectural Inspiration & Originality Statement

The concept of extracting music streaming metadata to build analytical pipelines is a well-established educational paradigm in data engineering.

This platform draws conceptual inspiration from educational Spotify ETL patterns, but **the repository records its own design decisions and incremental implementation; cloud IaC and analytical models remain planned**:
- **Educational Pattern**: Often consists of a single Python script overwriting daily JSON in S3 and loading flat tables into Snowflake or Athena without testing, versioning, or dimensional modeling.
- **This Platform's Planned Architecture**: Production-oriented concepts at portfolio scale:
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
- [Spotify Web API: Get Playlist Items Reference (`/v1/playlists/{id}/items`)](https://developer.spotify.com/documentation/web-api/reference/get-playlists-items)
- [Spotify Web API: Authorization Code Flow & Scopes](https://developer.spotify.com/documentation/web-api/concepts/authorization)
- [Spotify Web API: Working with Playlists & snapshot_id](https://developer.spotify.com/documentation/web-api/concepts/playlists)
- [Spotify Web API: February 2026 Migration Guide & Changelogs](https://developer.spotify.com/documentation/web-api)

### Apache Spark & AWS Glue
- [AWS Glue 5.1 Release Notes & Runtime Specifications (Spark 3.5.6, Python 3.11)](https://docs.aws.amazon.com/glue/latest/dg/release-notes.html)
- [Migrating to AWS Glue Version 5.1](https://docs.aws.amazon.com/glue/latest/dg/migrating-version-51.html)
- [Apache Spark 3.5 Documentation](https://spark.apache.org/docs/3.5.6/)
- [AWS Lambda Pricing (verify account eligibility and current rates)](https://aws.amazon.com/lambda/pricing/)

### Apache Airflow 3.x
- [Apache Airflow Release Notes](https://airflow.apache.org/docs/apache-airflow/stable/release_notes.html)
- [Airflow Task SDK Documentation (`airflow.sdk`)](https://airflow.apache.org/docs/task-sdk/stable/)
- [Airflow 3 Deadline Alerts (Replacing Legacy SLAs)](https://airflow.apache.org/docs/apache-airflow/stable/howto/deadline-alerts.html)
- [Upgrading from Airflow 2 to Airflow 3](https://airflow.apache.org/docs/apache-airflow/stable/installation/upgrading_to_airflow3.html)

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


## 3. Source and Runtime Review (2026-09-07)

| Contract | Official evidence | Repository decision |
| --- | --- | --- |
| Refresh lifecycle | [Spotify refresh guide](https://developer.spotify.com/documentation/web-api/tutorials/refreshing-tokens) | ADR-0007: periodic reauthorization; rotation is not grant renewal |
| Playlist access and shape | [Playlist items](https://developer.spotify.com/documentation/web-api/reference/get-playlists-items) | Owner/collaborator, `/items`, `item`, maximum 50 |
| Source version | [Playlist metadata](https://developer.spotify.com/documentation/web-api/reference/get-playlist) | Read `snapshot_id` from metadata before pagination and after each page |
| Analytics restrictions | [Policy III.13](https://developer.spotify.com/policy), [Terms II.8](https://developer.spotify.com/terms) | [ADR-0008](adr/0008-synthetic-analytics-and-source-use-boundary.md): fully synthetic analytics; live analytical use unresolved |
| Glue 5.1 runtime | [Glue versions](https://docs.aws.amazon.com/glue/latest/dg/release-notes.html) | Spark 3.5.6 / Python 3.11; separate from local Python 3.12 package |
| Deadline Alerts | [Airflow Deadline Alerts guide](https://airflow.apache.org/docs/apache-airflow/stable/howto/deadline-alerts.html) | Target >=3.1,<4; exact runtime/provider pins belong to M6 |
| Backfill CLI | [Airflow 3.1.0 CLI](https://airflow.apache.org/docs/apache-airflow/3.1.0/cli-and-env-variables-ref.html#backfill) | RUNBOOK example is version-specific; recheck at exact runtime pin |

The review checks API/runtime documentation, not live API behavior or contractual
approval. Cost figures elsewhere are planning assumptions; no current price quote,
Free Tier entitlement, benchmark, or cloud bill is established by this review.
