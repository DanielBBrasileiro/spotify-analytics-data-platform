"""Load the real Airflow 3 DAG without cloud connections or scheduler metadata."""

import json
import sys
from pathlib import Path

import pytest
from airflow.models.dagbag import DagBag

ROOT = Path(__file__).parents[2]


def test_dag_loads_and_every_mapped_gate_blocks_dbt():
    bag = DagBag(dag_folder=str(ROOT / "airflow" / "dags"), include_examples=False)
    assert bag.import_errors == {}
    dag = bag.dags["spotify_daily_snapshot"]
    assert dag.max_active_runs == 1
    assert dag.catchup is False
    assert dag.schedule is None
    assert dag.deadline is not None
    assert len(dag.deadline) == 1
    assert dag.deadline[0].interval.total_seconds() == 7200
    assert dag.on_failure_callback is not None
    assert "curate.await_landing" in dag.get_task("transform").upstream_task_ids
    assert "curate.await_glue" in dag.get_task("curate.await_landing").upstream_task_ids
    assert dag.get_task("curate.submit").retries == 0
    assert dag.get_task("prepare").retries == 3
    assert dag.get_task("prepare").retry_delay.total_seconds() == 300
    assert dag.get_task("prepare").retry_exponential_backoff is True
    assert dag.get_task("curate.await_landing").mode == "reschedule"
    assert dag.get_task("report").trigger_rule.value == "all_done"
    assert {task.task_id for task in dag.leaves} == {"report"}


@pytest.mark.parametrize("reject_landing", [False, True])
def test_real_dag_run_enforces_gate_and_reports_upstream_failure(
    monkeypatch, tmp_path, reject_landing
):
    """Run the actual scheduler/Task SDK loop with only cloud boundaries substituted."""
    from airflow.utils import db

    from airflow import settings
    from tests.orchestration.test_service_adapters import tasks

    # Never initialize a developer's default Airflow metadata database.
    metadata_uri = str(settings.SQL_ALCHEMY_CONN)
    project_tmp = str((ROOT / "tmp").resolve())
    assert "spotify-airflow" in metadata_uri or project_tmp in metadata_uri
    db.initdb()
    monkeypatch.setenv("AIRFLOW__CORE__DAGS_FOLDER", str(ROOT / "airflow/dags"))
    monkeypatch.setenv("AIRFLOW__CORE__HOSTNAME_CALLABLE", "socket.gethostname")
    monkeypatch.setattr(settings, "DAGS_FOLDER", str(ROOT / "airflow/dags"))
    monkeypatch.setitem(sys.modules, "spotify_tasks", tasks)
    monkeypatch.setenv("SPOTIFY_LAKE_BUCKET", "test-bucket")
    monkeypatch.setenv("SPOTIFY_GLUE_JOB_NAME", "test-job")
    monkeypatch.setenv("SNOWFLAKE_ACCOUNT", "offline")
    monkeypatch.setenv("SNOWFLAKE_USER", "offline")
    monkeypatch.setenv("SNOWFLAKE_PASSWORD", "offline-placeholder")
    monkeypatch.setenv("PIPELINE_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    source = {
        "playlist_id": "1" * 22,
        "spotify_snapshot_id": "cc0-sim-test",
        "source_provenance": {"temporal_state": "synthetic"},
        "items": [{"item": {"type": "track"}}],
    }
    (tmp_path / "bronze.json").write_text(json.dumps(source))
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "source": {"license": "CC0-1.0"},
                "records": [
                    {
                        **{key: source[key] for key in ("playlist_id", "spotify_snapshot_id")},
                        "snapshot_date": "2026-09-10",
                        "ingestion_date": "2026-09-10",
                        "snapshot_timestamp": "2026-09-10T12:00:00+00:00",
                        "bronze_relative_path": "bronze.json",
                    }
                ],
            }
        )
    )
    monkeypatch.setenv("DEMO_MANIFEST_PATH", str(manifest))
    data = json.loads(manifest.read_text())
    data["records"].append(
        {
            **data["records"][0],
            "snapshot_date": "2026-09-11",
            "snapshot_timestamp": "2026-09-11T12:00:00+00:00",
        }
    )
    manifest.write_text(json.dumps(data))
    calls = []
    monkeypatch.setattr(tasks, "upload_bronze", lambda record, bucket: record)
    monkeypatch.setattr(
        tasks,
        "submit_glue",
        lambda record, bucket, name: {
            "record": record,
            "job_name": name,
            "job_run_id": "jr_test",
        },
    )
    monkeypatch.setattr(tasks, "glue_finished", lambda job: True)

    def check(*args):
        calls.append("gate")
        if reject_landing:
            raise ValueError("Duplicated physical rows")
        return True

    def build(plan):
        calls.append("dbt")
        return {"nodes_passed": 1}

    monkeypatch.setattr(tasks, "check_landing", check)
    monkeypatch.setattr(tasks, "build_dbt", build)
    bag = DagBag(dag_folder=str(ROOT / "airflow/dags"), include_examples=False)
    dag = bag.dags["spotify_daily_snapshot"]
    for node in dag.tasks:
        node.retries = 0
    # Airflow 3.2.2 dag.test()/SQLite has a Deadline serialization bug;
    # the real scheduler/Postgres path is validated separately by DAG loading.
    dag.deadline = []
    run = dag.test(run_conf={"start_date": "2026-09-10", "end_date": "2026-09-11"})
    assert run.state == ("failed" if reject_landing else "success")
    assert calls == (["gate", "gate"] if reject_landing else ["gate", "gate", "dbt"])
    report = json.loads(next((tmp_path / "artifacts").glob("*/run-summary.json")).read_text())
    assert report["status"] == run.state
