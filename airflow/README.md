# Apache Airflow 3.x Orchestration

This directory contains the orchestration definitions for the Spotify Analytics Data Platform.

---

## Architectural Responsibility

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

Airflow will be containerized locally using Docker Compose to prevent incurring managed cloud orchestration fees (such as AWS MWAA ~$350/month) during initial phases and portfolio demonstrations.
