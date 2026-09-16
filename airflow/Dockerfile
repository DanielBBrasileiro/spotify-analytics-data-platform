FROM python:3.12-slim-bookworm AS dbt-builder

# dbt's experimental parser needs a Rust toolchain on native ARM64 builds. Keep
# compilers out of the runtime image by building the isolated dbt venv here.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential cargo rustc \
    && rm -rf /var/lib/apt/lists/*
COPY dbt/requirements-dev.txt /tmp/dbt-requirements.txt
RUN python -m venv /opt/airflow/dbt-venv \
    && /opt/airflow/dbt-venv/bin/pip install --no-cache-dir -r /tmp/dbt-requirements.txt

FROM python:3.12-slim-bookworm

ENV AIRFLOW_HOME=/opt/airflow \
    PYTHONPATH=/opt/spotify/src:/opt/spotify/runtime \
    DBT_EXECUTABLE=/opt/airflow/dbt-venv/bin/dbt \
    DBT_SEND_ANONYMOUS_USAGE_STATS=false

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl git libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 50000 airflow \
    && useradd --uid 50000 --gid 50000 --home-dir /home/airflow --create-home airflow \
    && mkdir -p /opt/airflow /opt/spotify \
    && chown -R airflow:airflow /opt/airflow /opt/spotify

COPY airflow/requirements.txt /tmp/airflow-requirements.txt
RUN pip install --no-cache-dir \
      "apache-airflow==3.2.2" \
      -r /tmp/airflow-requirements.txt \
      --constraint https://raw.githubusercontent.com/apache/airflow/constraints-3.2.2/constraints-3.12.txt

COPY --from=dbt-builder --chown=airflow:airflow /opt/airflow/dbt-venv /opt/airflow/dbt-venv
COPY --chown=airflow:airflow src /opt/spotify/src
COPY --chown=airflow:airflow dbt /opt/spotify/dbt
COPY --chown=airflow:airflow airflow/profiles /opt/spotify/profiles
COPY --chown=airflow:airflow airflow/runtime /opt/spotify/runtime
COPY --chown=airflow:airflow airflow/dags /opt/airflow/dags

USER airflow
RUN /opt/airflow/dbt-venv/bin/dbt deps --project-dir /opt/spotify/dbt \
    && mkdir -p /opt/airflow/state /opt/airflow/artifacts /opt/airflow/logs

ENTRYPOINT ["airflow"]
CMD ["standalone"]
