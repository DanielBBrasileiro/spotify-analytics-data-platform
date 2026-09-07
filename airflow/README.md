# Apache Airflow 3.x Orchestration

This directory currently contains only this design README. DAGs, Docker Compose, provider pins, and alerts are planned for M6.

Analytical demonstrations use fully synthetic data under [ADR-0008](../docs/adr/0008-synthetic-analytics-and-source-use-boundary.md).
The responsibilities and directory structure below are targets, not current implementation.

---

## Planned Architectural Responsibility

Per **ADR-0001**, Apache Airflow 3.x operates strictly as an **Orchestrator**, not an execution engine.

Heavy compute, complex data extraction, distributed ETL, and warehouse transformations are explicitly delegated to their dedicated services:
- Extraction: **AWS Lambda** (invoked via task execution triggers)
- Bronze-to-Silver ETL: **AWS Glue 5.1 (Apache Spark 3.5.6 / Python 3.11)**
- Silver-to-Landing Ingestion: **Snowpipe / Snowflake COPY**
- Analytical Modeling: **dbt Core (executing pushdown SQL in Snowflake)**
- Data Quality Assertions: **dbt tests & pipeline validation gates**

Airflow coordinates task sequencing, state checking, idempotency validation, Deadline Alerts, and automated retries.

---

## Airflow 3.x Architectural Alignment

- **Task SDK (`airflow.sdk`)**: DAGs are authored using the Airflow 3 Task SDK, decoupling DAG authoring from scheduler internals.
- **Deadline Alerts**: Replaces legacy Airflow 2 SLAs with proactive Deadline Alerts evaluated by the scheduler loop.
- **Standalone DAG Processor**: Operates in a service-oriented architecture with isolated DAG bundle evaluation.

---

## Planned Directory Structure

```
airflow/
├── dags/
│   ├── spotify_daily_snapshot_dag.py     # Main end-to-end orchestration DAG (Airflow 3 Task SDK)
│   └── spotify_backfill_dag.py           # Historical snapshot backfill DAG
├── plugins/                              # Custom operators and sensors
│   ├── sensors/
│   │   └── s3_bronze_object_sensor.py
│   └── operators/
│       └── snowflake_validation_operator.py
├── docker-compose.yml                    # Local Airflow 3.x deployment
├── Dockerfile                            # Custom image containing AWS and Snowflake CLI/SDKs
└── requirements.txt                      # Airflow provider packages (apache-airflow-providers-amazon, etc.)
```

---

## Local Development (Docker Compose)

Airflow will be containerized locally using Docker Compose to prevent incurring managed cloud orchestration fees (such as AWS MWAA; consult current pricing before comparing costs) during initial phases and portfolio demonstrations.


## Runtime selection

Target Airflow **>=3.1,<4**: Deadline Alerts were introduced in 3.1 and remain
experimental in the reviewed [official guide](https://airflow.apache.org/docs/apache-airflow/stable/howto/deadline-alerts.html); the label
"3.x" alone does not establish compatibility. M6 must select and pin an exact
Airflow release, Task SDK, providers, and container dependencies together.
Nothing is pinned or installed by this README. The
[RUNBOOK](../docs/RUNBOOK.md) uses version-specific Airflow 3.1.0 CLI syntax as a
reference and must be rechecked against the selected runtime.
