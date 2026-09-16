"""Service-boundary regression tests; no AWS/Snowflake credentials or network."""

import hashlib
import importlib.util
import io
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from tests.unit.test_orchestration_contracts import completion

ROOT = Path(__file__).parents[2]
SPEC = importlib.util.spec_from_file_location(
    "spotify_tasks", ROOT / "airflow/runtime/spotify_tasks.py"
)
tasks = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tasks)


@pytest.fixture
def record(tmp_path):
    path = tmp_path / "bronze.json"
    path.write_bytes(b"source")
    return {
        "local_path": str(path),
        "sha256": hashlib.sha256(b"source").hexdigest(),
        "bronze_key": "bronze/new-run.json",
        "pipeline_run_id": "123e4567-e89b-42d3-a456-426614174000",
        "playlist_id": "1" * 22,
        "snapshot_date": "2026-09-10",
        "ingestion_date": "2026-09-10",
        "snapshot_timestamp": "2026-09-10T12:00:00+00:00",
        "completion_key": "metadata/curation/run/complete.json",
    }


class ClientError(Exception):
    def __init__(self, code):
        self.response = {"Error": {"Code": code}}


def test_upload_is_immutable_and_retry_verifies_exact_bytes(monkeypatch, record):
    client = MagicMock()
    client.exceptions = SimpleNamespace(ClientError=ClientError)
    monkeypatch.setattr(tasks, "aws", lambda *a, **kw: client)
    assert tasks.upload_bronze(record, "bucket") == record
    assert client.put_object.call_args.kwargs["IfNoneMatch"] == "*"
    client.put_object.side_effect = ClientError("PreconditionFailed")
    client.get_object.return_value = {"Body": io.BytesIO(b"source")}
    assert tasks.upload_bronze(record, "bucket") == record
    client.get_object.return_value = {"Body": io.BytesIO(b"other")}
    with pytest.raises(ValueError, match="different"):
        tasks.upload_bronze(record, "bucket")
    client.put_object.side_effect = ClientError("AccessDenied")
    with pytest.raises(ClientError):
        tasks.upload_bronze(record, "bucket")
    Path(record["local_path"]).write_bytes(b"modified")
    with pytest.raises(ValueError, match="changed"):
        tasks.upload_bronze(record, "bucket")


def test_glue_submission_claim_prevents_resubmission_and_disables_sdk_retries(monkeypatch, record):
    glue, s3 = MagicMock(), MagicMock()
    glue.get_job.return_value = {"Job": {"MaxRetries": 0}}
    glue.start_job_run.return_value = {"JobRunId": "jr_test"}
    clients = MagicMock(side_effect=lambda name, **kw: glue if name == "glue" else s3)
    monkeypatch.setattr(tasks, "aws", clients)
    job = tasks.submit_glue(record, "bucket", "curation")
    assert job["job_run_id"] == "jr_test"
    assert clients.call_args_list[0].kwargs == {"retry_attempts": 0}
    assert s3.put_object.call_args.kwargs["IfNoneMatch"] == "*"
    assert glue.start_job_run.call_args.kwargs["JobRunQueuingEnabled"] is True
    assert "--completion-uri" in glue.start_job_run.call_args.kwargs["Arguments"]
    s3.put_object.side_effect = ClientError("PreconditionFailed")
    with pytest.raises(ClientError):
        tasks.submit_glue(record, "bucket", "curation")
    assert glue.start_job_run.call_count == 1
    glue.get_job.return_value = {"Job": {"MaxRetries": 2}}
    with pytest.raises(ValueError, match="MaxRetries"):
        tasks.submit_glue(record, "bucket", "curation")


@pytest.mark.parametrize(
    "state,expected", [("WAITING", False), ("RUNNING", False), ("SUCCEEDED", True)]
)
def test_glue_polling(monkeypatch, state, expected):
    client = MagicMock()
    client.get_job_run.return_value = {"JobRun": {"JobRunState": state}}
    monkeypatch.setattr(tasks, "aws", lambda *a, **kw: client)
    assert tasks.glue_finished({"job_name": "job", "job_run_id": "jr_test"}) is expected


@pytest.mark.parametrize("state", ["FAILED", "TIMEOUT", "STOPPED", "ERROR", "EXPIRED"])
def test_glue_failure_stops_pipeline(monkeypatch, state):
    client = MagicMock()
    client.get_job_run.return_value = {"JobRun": {"JobRunState": state}}
    monkeypatch.setattr(tasks, "aws", lambda *a, **kw: client)
    with pytest.raises(ValueError, match=state):
        tasks.glue_finished({"job_name": "job", "job_run_id": "jr_test"})


def test_readiness_reads_six_current_run_partitions_and_persists_evidence(
    monkeypatch, tmp_path, record
):
    inventory = completion(record)
    client = MagicMock()
    client.get_object.side_effect = lambda **kw: {
        "Body": io.BytesIO(json.dumps(inventory).encode())
    }
    client.get_job_run.return_value = {"JobRun": {"ExecutionTime": 12, "DPUSeconds": 24.0}}
    monkeypatch.setattr(tasks, "aws", lambda *a, **kw: client)
    monkeypatch.setenv("PIPELINE_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    connection = MagicMock()
    cursor = connection.__enter__.return_value.cursor.return_value.__enter__.return_value
    monkeypatch.setattr(tasks, "snowflake_connection", lambda: connection)
    landed = [
        [(files[0]["key"].removeprefix("silver/"), 1, 1)]
        for files in inventory["datasets"].values()
    ]
    cursor.fetchall.side_effect = [*landed[:-1], []]
    job = {"record": record, "job_name": "curation", "job_run_id": "jr_test"}
    assert tasks.check_landing(job, "bucket", "dag-run") is False
    cursor.fetchall.side_effect = landed
    assert tasks.check_landing(job, "bucket", "dag-run") is True
    sql, params = cursor.execute.call_args.args
    assert "STARTSWITH" in sql and "LIKE" not in sql
    assert record["pipeline_run_id"] in params[0]
    evidence = list((tmp_path / "artifacts").glob("*/landing-*.json"))
    assert evidence
    payload = json.loads(evidence[0].read_text())
    assert payload["glue_execution_time_seconds"] == 12
    assert payload["glue_dpu_seconds"] == 24.0
    inventory["rejected_items"] = 1
    with pytest.raises(ValueError, match="rejected"):
        tasks.check_landing(job, "bucket", "dag-run")


def test_dbt_build_captures_artifacts_and_rejects_warn_or_skipped_nodes(monkeypatch, tmp_path):
    monkeypatch.setenv("PIPELINE_ARTIFACT_ROOT", str(tmp_path))
    plan = {"airflow_run_id": "run", "start_date": "2026-09-10", "end_date": "2026-09-12"}
    statuses = ["success", "pass"]

    def run(command, **kwargs):
        assert command[1] == "build"
        assert json.loads(command[-1]) == {
            "start_date": plan["start_date"],
            "end_date": plan["end_date"],
        }
        assert kwargs["timeout"] == 1800
        target = Path(command[command.index("--target-path") + 1])
        target.mkdir(exist_ok=True)
        (target / "run_results.json").write_text(
            json.dumps(
                {
                    "results": [{"status": status} for status in statuses],
                    "elapsed_time": 2.5,
                }
            )
        )

    monkeypatch.setattr(tasks.subprocess, "run", run)
    assert tasks.build_dbt(plan)["nodes_passed"] == 2
    statuses[:] = ["warn"]
    with pytest.raises(ValueError, match="successful"):
        tasks.build_dbt(plan)
    statuses[:] = []
    with pytest.raises(ValueError):
        tasks.build_dbt(plan)

    def fail(*a, **kw):
        raise subprocess.CalledProcessError(1, "dbt")

    monkeypatch.setattr(tasks.subprocess, "run", fail)
    with pytest.raises(subprocess.CalledProcessError):
        tasks.build_dbt(plan)


def test_failure_callbacks_emit_sanitized_structured_json(capsys):
    task_instance = SimpleNamespace(
        dag_id="spotify_daily_snapshot",
        task_id="transform",
        run_id="manual__test",
        try_number=2,
    )
    context = {
        "task_instance": task_instance,
        "exception": RuntimeError("do-not-log-this-secret-message"),
    }
    payload = tasks.dag_failure_callback(context)
    rendered = capsys.readouterr().out.strip()
    assert json.loads(rendered) == payload
    assert payload["event"] == "DAG_FAILED"
    assert payload["exception_type"] == "RuntimeError"
    assert "do-not-log-this-secret-message" not in rendered

    deadline = tasks.deadline_missed_callback(context, deadline_name="completion")
    rendered = capsys.readouterr().out.strip()
    assert json.loads(rendered) == deadline
    assert deadline["event"] == "DAG_DEADLINE_MISSED"
    assert deadline["deadline_name"] == "completion"
