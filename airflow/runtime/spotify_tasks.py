"""Small service adapters used by Task SDK tasks; no work runs while importing a DAG."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from spotify_data_platform.orchestration.contracts import (
    DATASETS,
    landing_ready,
    run_key,
    validate_completion,
)


def aws(service, *, retry_attempts=3):
    import boto3
    from botocore.config import Config

    return boto3.client(
        service,
        region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
        config=Config(
            connect_timeout=10,
            read_timeout=30,
            retries={"mode": "standard", "max_attempts": retry_attempts},
        ),
    )


def snowflake_connection():
    import snowflake.connector

    auth = {}
    if os.environ.get("SNOWFLAKE_PRIVATE_KEY_PATH"):
        auth["private_key_file"] = os.environ["SNOWFLAKE_PRIVATE_KEY_PATH"]
        if os.environ.get("SNOWFLAKE_PRIVATE_KEY_PASSPHRASE"):
            auth["private_key_file_pwd"] = os.environ["SNOWFLAKE_PRIVATE_KEY_PASSPHRASE"]
    else:
        auth["password"] = os.environ["SNOWFLAKE_PASSWORD"]
    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        role="SPOTIFY_TRANSFORMER",
        database="SPOTIFY_ANALYTICS",
        schema="LANDING",
        warehouse="COMPUTE_WH",
        login_timeout=20,
        network_timeout=30,
        session_parameters={"STATEMENT_TIMEOUT_IN_SECONDS": 60},
        **auth,
    )


def artifact_dir(airflow_run_id):
    path = Path(os.environ.get("PIPELINE_ARTIFACT_ROOT", "/opt/airflow/artifacts"))
    path = path / run_key(airflow_run_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_report(airflow_run_id, filename, payload):
    directory = artifact_dir(airflow_run_id)
    pending = directory / f".{filename}.tmp"
    pending.write_text(json.dumps(payload, indent=2, default=str) + "\n")
    pending.replace(directory / filename)


def _airflow_context_value(context, name, default=None):
    """Read one safe scalar from callback context without serializing Airflow objects."""
    value = context.get(name, default) if isinstance(context, dict) else default
    if value is None:
        return default
    return str(value)


def _emit_airflow_event(event, context, **details):
    """Emit a compact structured event without exception text or credentials."""
    ti = context.get("task_instance") if isinstance(context, dict) else None
    dag_run = context.get("dag_run") if isinstance(context, dict) else None
    exception = context.get("exception") if isinstance(context, dict) else None
    payload = {
        "timestamp": datetime.now(UTC).isoformat(),
        "event": event,
        "component": "airflow",
        "status": "FAILED",
        "dag_id": getattr(ti, "dag_id", None) or getattr(dag_run, "dag_id", None),
        "task_id": getattr(ti, "task_id", None),
        "run_id": getattr(ti, "run_id", None)
        or getattr(dag_run, "run_id", None)
        or _airflow_context_value(context, "run_id"),
        "try_number": getattr(ti, "try_number", None),
        "exception_type": type(exception).__name__ if exception is not None else None,
        **details,
    }
    print(json.dumps(payload, separators=(",", ":"), default=str), flush=True)
    return payload


def dag_failure_callback(context):
    """DAG-level failure callback with sanitized structured context."""
    return _emit_airflow_event("DAG_FAILED", context)


def deadline_missed_callback(context, **kwargs):
    """Deadline Alert callback executed by Airflow after the run completion deadline."""
    return _emit_airflow_event("DAG_DEADLINE_MISSED", context, **kwargs)


def upload_bronze(record, bucket):
    body = Path(record["local_path"]).read_bytes()
    if hashlib.sha256(body).hexdigest() != record["sha256"]:
        raise ValueError("Bronze changed after planning.")
    client = aws("s3")
    try:
        client.put_object(
            Bucket=bucket,
            Key=record["bronze_key"],
            Body=body,
            ContentType="application/json",
            IfNoneMatch="*",
        )
    except client.exceptions.ClientError as exc:
        if exc.response["Error"]["Code"] != "PreconditionFailed":
            raise
        existing = client.get_object(Bucket=bucket, Key=record["bronze_key"])["Body"].read()
        if existing != body:
            raise ValueError("Immutable Bronze key already contains different data.") from exc
    return record


def submit_glue(record, bucket, job_name):
    # This task has retries=0. An ambiguous StartJobRun response must be investigated,
    # never blindly repeated against the same physical Silver publication prefix.
    # Glue's own MaxRetries must also be zero (preflight below).
    client = aws("glue", retry_attempts=0)
    job = client.get_job(JobName=job_name)["Job"]
    if job.get("MaxRetries", 0) != 0:
        raise ValueError("The orchestration Glue job must have MaxRetries=0.")
    # Keep an immutable claim even if StartJobRun times out. Never submit twice when
    # clearing a task: investigate Glue and replay in a new Dag run with fresh IDs.
    aws("s3").put_object(
        Bucket=bucket,
        Key=record["completion_key"].replace("/complete.json", "/submission.json"),
        Body=json.dumps(
            {"job_name": job_name, "pipeline_run_id": record["pipeline_run_id"]}
        ).encode(),
        ContentType="application/json",
        IfNoneMatch="*",
    )
    response = client.start_job_run(
        JobName=job_name,
        JobRunQueuingEnabled=True,
        Timeout=15,
        Arguments={
            "--bronze-path": f"s3://{bucket}/{record['bronze_key']}",
            "--silver-root": f"s3://{bucket}",
            "--pipeline-run-id": record["pipeline_run_id"],
            "--snapshot-date": record["snapshot_date"],
            "--snapshot-timestamp": record["snapshot_timestamp"],
            "--ingestion-date": record["ingestion_date"],
            "--output-partitions": "1",
            "--completion-uri": f"s3://{bucket}/{record['completion_key']}",
        },
    )
    return {"record": record, "job_name": job_name, "job_run_id": response["JobRunId"]}


def glue_finished(job):
    run = aws("glue").get_job_run(JobName=job["job_name"], RunId=job["job_run_id"])["JobRun"]
    state = run["JobRunState"]
    if state in {"FAILED", "STOPPED", "TIMEOUT", "ERROR", "EXPIRED"}:
        raise ValueError(f"Glue run {job['job_run_id']} ended in {state}.")
    return state == "SUCCEEDED"


def check_landing(job, bucket, airflow_run_id):
    record = job["record"]
    raw = aws("s3").get_object(Bucket=bucket, Key=record["completion_key"])["Body"].read()
    completion = json.loads(raw)
    datasets = validate_completion(completion, record)
    if completion["rejected_items"]:
        raise ValueError("Demo quality gate rejected malformed source items; inspect Glue output.")
    checks = {}
    with snowflake_connection() as connection, connection.cursor() as cursor:
        for dataset in DATASETS:
            prefix = (
                f"{dataset}/ingestion_date={record['ingestion_date']}/"
                f"run_id={record['pipeline_run_id']}/playlist_id={record['playlist_id']}/"
            )
            # Prefix equality, not LIKE: underscores in physical keys are literals.
            cursor.execute(
                f"SELECT _FILE_NAME, COUNT(*), COUNT(DISTINCT _FILE_ROW_NUMBER) "
                f"FROM SPOTIFY_ANALYTICS.LANDING.LANDING_{dataset.upper()} "
                "WHERE STARTSWITH(_FILE_NAME, %s) OR STARTSWITH(_FILE_NAME, %s) "
                "GROUP BY _FILE_NAME",
                (prefix, "silver/" + prefix),
            )
            checks[dataset] = landing_ready(datasets[dataset], cursor.fetchall())
    ready = all(checks.values())
    glue_run = {}
    if ready:
        glue_run = aws("glue").get_job_run(JobName=job["job_name"], RunId=job["job_run_id"])[
            "JobRun"
        ]
    write_report(
        airflow_run_id,
        f"landing-{record['pipeline_run_id']}.json",
        {
            "ready": ready,
            "datasets": checks,
            "completion": completion,
            "glue_job_run_id": job["job_run_id"],
            "glue_execution_time_seconds": glue_run.get("ExecutionTime"),
            "glue_dpu_seconds": glue_run.get("DPUSeconds"),
        },
    )
    return ready


def build_dbt(plan):
    directory = artifact_dir(plan["airflow_run_id"])
    target = directory / "dbt"
    command = [
        os.environ.get("DBT_EXECUTABLE", "/opt/dbt-venv/bin/dbt"),
        "build",
        "--project-dir",
        os.environ.get("DBT_PROJECT_DIR", "/opt/spotify/dbt"),
        "--profiles-dir",
        os.environ.get("DBT_PROFILES_DIR", "/opt/spotify/profiles"),
        "--target-path",
        str(target),
        "--log-path",
        str(directory / "dbt-logs"),
        "--vars",
        json.dumps({"start_date": plan["start_date"], "end_date": plan["end_date"]}),
    ]
    with (directory / "dbt-output.log").open("w") as output:
        subprocess.run(
            command,
            check=True,
            stdout=output,
            stderr=subprocess.STDOUT,
            timeout=1800,
            env={**os.environ, "DBT_SEND_ANONYMOUS_USAGE_STATS": "false"},
        )
    results = json.loads((target / "run_results.json").read_text())
    nodes = results["results"]
    if not nodes or any(node["status"] not in {"success", "pass"} for node in nodes):
        raise ValueError("dbt did not produce a fully successful build.")
    report = {
        "nodes_passed": len(nodes),
        "elapsed_seconds": results["elapsed_time"],
        "completed_at": datetime.now(UTC).isoformat(),
    }
    write_report(plan["airflow_run_id"], "dbt-summary.json", report)
    return report
