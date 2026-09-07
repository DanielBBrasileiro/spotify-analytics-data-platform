# ADR-0004: Use Snowflake as Central Analytical Data Warehouse

## Status
Accepted

## Context
The platform requires an analytical storage and compute engine capable of:
1. Scalable SQL query processing for Kimball dimensional modeling and historical trend analysis.
2. Native integration with dbt Core for versioned transformations, lineage, and documentation.
3. Automated continuous ingestion from Amazon S3 via serverless mechanisms.
4. Direct connectivity to BI reporting tools (Power BI).
5. Elastic compute scaling with aggressive auto-suspend to reduce idle costs within a measured portfolio budget; auto-suspend does not enforce a total spending cap.

## Decision
We decide to use **Snowflake** as the primary analytical data warehouse, planned for AWS US East (`us-east-1` co-located with our S3 data lake).

Planned configuration (no DDL or deployed warehouse exists in this repository):
1. **Separation of Compute and Storage**: Data persists in Snowflake micro-partitions while compute operates independently via virtual warehouses.
2. **Layered Schema Hierarchy**:
   - `LANDING`: Snowpipe destination loading directly from S3 Silver Parquet.
   - `STAGING`: Cleaned, type-validated views/ephemeral models managed by dbt.
   - `CORE`: Dimensional star schema (`dim_*`, `fact_*`, `bridge_*`).
   - `MARTS`: Aggregated business models serving Power BI.
3. **Automated Continuous Ingestion**: Snowpipe uses AWS SQS and S3 event notifications for automated, event-driven loading.
4. **Cost Governance**: Single `COMPUTE_WH` configured as `X-Small`, `AUTO_SUSPEND = 60` seconds, and `AUTO_RESUME = TRUE`.

## Alternatives Considered
- **Amazon Redshift Serverless**:
  - *Pros*: Native AWS ecosystem integration.
  - *Cons*: Base capacity units (RPUs) incur a minimum floor cost that can rapidly exceed the $20/month budget; less flexible auto-suspend granularity compared to Snowflake per-second billing.
- **DuckDB (Local / In-Process)**:
  - *Pros*: Completely free, lightning fast for local workloads.
  - *Cons*: Does not demonstrate enterprise cloud warehouse architecture, multi-user role-based access control, Snowpipe ingestion, or remote BI publishing required for senior portfolio evaluations.
- **Google BigQuery / Databricks SQL**:
  - *Pros*: Robust enterprise analytical engines.
  - *Cons*: Snowflake offers the most direct industry alignment for cross-cloud S3 integration, dbt ecosystem compatibility, and granular virtual warehouse credit control.

## Consequences

### Positive Consequences
- **Enterprise Standard**: Demonstrates industry-standard skills (Snowpipe, storage integrations, RBAC, dbt on Snowflake).
- **Reduced Idle Warehouse Cost**: Planned auto-suspension reduces idle warehouse consumption. Storage and serverless services are separate cost categories; no billed run or total cost cap has been validated.
- **Optimized for dbt**: Snowflake SQL provides full support for window functions, surrogate key generation, and incremental merges.

### Negative Consequences
- **Cloud Account Management**: Requires maintaining a Snowflake account and managing cross-cloud IAM storage integrations.
- **Credit Vigilance**: Neglecting warehouse auto-suspend or running unoptimized long queries can exhaust credits.

## Risks
- Unexpected warehouse runs from automated polling. Mitigated by setting aggressive statement timeouts, resource monitors, and ensuring Airflow queries use cached results or trigger warehouse activation only during scheduled pipeline runs.

## Review Conditions
Review if budget limits cannot be maintained during multi-developer scaling, in which case a hybrid approach (DuckDB for local development, Snowflake for staged deployment) would be evaluated.
