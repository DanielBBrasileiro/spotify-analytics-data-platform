# References, Inspiration & Attribution

This document records the architectural references, foundational concepts, and official documentation that informed the design of the **Spotify Analytics Data Platform**.

---

## 1. Architectural Inspiration & Originality Statement

The concept of extracting music streaming metadata to build analytical pipelines is a well-established educational paradigm in data engineering.

This platform draws conceptual inspiration from educational Spotify ETL patterns (specifically basic Lambda-to-S3 pipelines), but **the architectural implementation, infrastructure as code, data models, and codebase are entirely original**:
- **Educational Pattern**: Often consists of a single Python script overwriting daily JSON in S3 and loading flat tables into Snowflake or Athena without testing or dimensional modeling.
- **This Platform's Architecture**: Engineered to enterprise standards:
  - Strict separation between Airflow orchestration and external compute execution.
  - Multi-tiered data lake (Bronze immutable raw JSON -> Silver normalized Parquet).
  - PySpark distributed unnesting of deeply nested arrays.
  - Automated continuous Snowflake ingestion via Snowpipe.
  - Kimball dimensional star schema (`dim_*`, `fact_*`, `bridge_*`) managed via dbt Core.
  - Historical longitudinal snapshot modeling preserving daily track placement, churn, and retention.
  - Zero-spend local development workflows and explicit cost governance.

---

## 2. Official Documentation & Specifications

### Spotify Web API
- [Spotify Developer Platform Documentation](https://developer.spotify.com/documentation/web-api)
- [Spotify Web API: Get Playlist Items Reference](https://developer.spotify.com/documentation/web-api/reference/get-playlists-tracks)
- [Spotify Web API Authorization Guide](https://developer.spotify.com/documentation/web-api/concepts/authorization)

### Apache Spark & AWS Glue
- [Apache Spark 3.3+ Documentation](https://spark.apache.org/docs/latest/)
- [AWS Glue Developer Guide](https://docs.aws.amazon.com/glue/latest/dg/what-is-glue.html)
- [AWS Glue PySpark Programming Reference](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-python.html)

### Snowflake & Snowpipe
- [Snowflake Continuous Data Pipelines (Snowpipe)](https://docs.snowflake.com/en/user-guide/data-load-snowpipe-intro)
- [Snowflake External Stages & Storage Integrations for S3](https://docs.snowflake.com/en/user-guide/data-load-s3-config-storage-integration)
- [Snowflake Best Practices for Cost Optimization](https://docs.snowflake.com/en/user-guide/cost-understanding-overall)

### dbt Core
- [dbt Core Documentation](https://docs.getdbt.com/docs/build/documentation)
- [dbt-snowflake Adapter Reference](https://docs.getdbt.com/reference/warehouse-setups/snowflake-setup)
- [Dimensional Modeling with dbt Best Practices](https://docs.getdbt.com/blog/kimball-dimensional-modeling)

### Apache Airflow
- [Apache Airflow 2.x Architecture & Best Practices](https://airflow.apache.org/docs/apache-airflow/stable/best-practices.html)
- [Amazon Provider Package for Airflow](https://airflow.apache.org/docs/apache-airflow-providers-amazon/stable/index.html)

### Infrastructure as Code & Tooling
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [Ruff Linter & Formatter](https://docs.astral.sh/ruff/)
- [pytest Testing Framework](https://docs.pytest.org/en/stable/)
