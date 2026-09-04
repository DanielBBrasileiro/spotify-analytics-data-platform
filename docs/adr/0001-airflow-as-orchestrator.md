# ADR-0001: Use Apache Airflow as Orchestrator Rather Than Execution Engine

## Status
Accepted

## Context
In data engineering architectures, Apache Airflow is frequently misconfigured as a monolithic execution engine where DAGs run heavy extraction logic, parse multi-megabyte JSON payloads in worker memory, execute complex pandas transformations, or run compute-intensive queries. This pattern leads to worker memory exhaustion (OOM), task concurrency bottlenecks, fragile dependency graphs, and tight coupling between orchestration scheduling and data processing runtimes.

In our Spotify Analytics Data Platform, workloads include API pagination, semi-structured JSON ingestion, distributed PySpark array explosion, and multi-layer SQL dimensional transformations.

## Decision
We decide to use **Apache Airflow strictly as an Orchestrator**, delegating all compute, extraction, and transformation workloads to dedicated external platforms:
1. **Extraction**: Delegated to AWS Lambda (`LambdaInvokeFunctionOperator`).
2. **Semi-structured transformation & normalization**: Delegated to AWS Glue / Apache Spark (`GlueJobOperator`).
3. **Data warehouse loading**: Delegated to Snowpipe / Snowflake native commands.
4. **Dimensional modeling & analytical metrics**: Delegated to dbt Core via Snowflake pushdown (`DbtRunOperator` / Bash execution of dbt CLI).
5. **Quality assertions**: Executed via dbt tests and external quality gate operators.

Airflow's responsibility is confined to scheduling, task sequencing, dependency management, sensor polling, SLA monitoring, and alerting.

## Alternatives Considered
- **Monolithic Airflow Execution (PythonOperator + Pandas)**:
  - *Pros*: Simple single-service deployment without external AWS/Glue dependencies.
  - *Cons*: High risk of Out-Of-Memory errors, inability to scale horizontally for larger historical backfills, polluted Airflow worker environments, high maintenance overhead.
- **AWS Step Functions**:
  - *Pros*: Fully serverless orchestration native to AWS.
  - *Cons*: Limited cross-cloud and local developer ecosystem, proprietary JSON state machine definition, lower visibility and analytical observability compared to Airflow's rich UI.
- **Prefect / Dagster**:
  - *Pros*: Modern Python-first orchestration paradigms.
  - *Cons*: While excellent tools, Apache Airflow remains the enterprise industry standard sought after in international Senior Data Engineering roles.

## Consequences

### Positive Consequences
- **Worker Stability**: Airflow workers require minimal RAM and CPU since they only manage task state and poll APIs.
- **Decoupled Lifecycles**: Spark transformations, Lambda extractors, and dbt models can be modified, tested, and versioned independently from orchestration DAGs.
- **Portability & Cost**: Airflow can run locally in Docker Compose during development with zero cloud cost, communicating with AWS and Snowflake via standard credentials.
- **Scalability**: Data volume increases affect AWS Glue and Snowflake compute, leaving Airflow unaffected.

### Negative Consequences
- **Asynchronous Task Complexity**: Airflow tasks must invoke external jobs and poll for completion (e.g., using sensors or deferrable operators).
- **Environment Management**: Requires configuring IAM credentials, connection IDs, and role permissions between Airflow, AWS, and Snowflake.

## Risks
- Operational lag if polling intervals for Glue jobs or Snowpipe loads are configured inefficiently.
- Failure propagation: Clear error bubbling from AWS Glue or Snowflake back into Airflow task logs must be explicitly engineered.

## Review Conditions
This decision will be reviewed if pipeline execution moves entirely to event-driven real-time streaming, or if serverless orchestration (e.g., AWS Step Functions) becomes mandatory due to infrastructure cost constraints.
