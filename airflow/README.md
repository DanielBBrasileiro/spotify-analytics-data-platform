# Apache Airflow Orchestration

This directory contains the orchestration definitions for the Spotify Analytics Data Platform.

---

## Architectural Responsibility

Per **ADR-0001**, Apache Airflow operates strictly as an **Orchestrator**, not an execution engine.

Heavy compute, complex data extraction, distributed ETL, and warehouse transformations are explicitly delegated to their dedicated services:
- Extraction: **AWS Lambda**
- Bronze-to-Silver ETL: **AWS Glue (Apache Spark / PySpark)**
- Silver-to-Landing Ingestion: **Snowpipe / Snowflake COPY**
- Analytical Modeling: **dbt Core (executing pushdown SQL in Snowflake)**
- Data Quality Assertions: **dbt tests & pipeline validation gates**

Airflow coordinates task sequencing, state checking, idempotency validation, failure alerts, and automated retries.

---

## Planned Directory Structure

```
airflow/
├── dags/
│   ├── spotify_daily_snapshot_dag.py     # Main end-to-end orchestration DAG
│   └── spotify_backfill_dag.py           # Historical snapshot backfill DAG
├── plugins/                              # Custom operators and sensors (if required)
│   ├── sensors/
│   │   └── s3_bronze_object_sensor.py
│   └── operators/
│       └── snowflake_validation_operator.py
├── docker-compose.yml                    # Local Airflow deployment (Celery/Local executor)
├── Dockerfile                            # Custom image containing AWS and Snowflake CLI/SDKs
└── requirements.txt                      # Airflow provider packages (apache-airflow-providers-amazon, etc.)
```

---

## Local Development (Docker Compose)

Airflow will be containerized locally using Docker Compose to prevent incurring managed cloud orchestration fees (such as AWS MWAA) during initial phases and portfolio demonstrations.
