"""Offline contracts for unified telemetry and safe recovery CLIs."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from spotify_data_platform.orchestration.contracts import DATASETS, run_key
from spotify_data_platform.orchestration.reporting import (
    build_run_report,
    locate_run_directory,
    persist_run_report,
    upload_run_report,
    validate_run_report,
)

ROOT = Path(__file__).parents[2]


def load_script(name):
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_run(root: Path, airflow_run_id="manual__test") -> Path:
    directory = root / run_key(airflow_run_id)
    directory.mkdir(parents=True)
    pipeline_run_id = "123e4567-e89b-42d3-a456-426614174000"
    record = {
        "pipeline_run_id": pipeline_run_id,
        "spotify_snapshot_id": "cc0-sim-test",
        "snapshot_date": "2026-09-10",
        "playlist_id": "1" * 22,
        "records_extracted": 12,
    }
    datasets = {
        dataset: [
            {
                "key": f"silver/{dataset}/part.parquet",
                "rows": 12 if dataset != "playlist_observations" else 1,
            }
        ]
        for dataset in DATASETS
    }
    completion = {
        "schema_version": 1,
        "pipeline_run_id": pipeline_run_id,
        "snapshot_date": "2026-09-10",
        "ingestion_date": "2026-09-10",
        "playlist_id": "1" * 22,
        "rejected_items": 0,
        "datasets": datasets,
    }
    (directory / "plan.json").write_text(
        json.dumps(
            {
                "airflow_run_id": airflow_run_id,
                "start_date": "2026-09-10",
                "end_date": "2026-09-10",
                "source_type": "cc0_demo",
                "temporal_state": "synthetic",
            }
        )
    )
    (directory / f"glue-{pipeline_run_id}.json").write_text(
        json.dumps({"record": record, "job_run_id": "jr_test"})
    )
    (directory / f"landing-{pipeline_run_id}.json").write_text(
        json.dumps(
            {
                "ready": True,
                "datasets": dict.fromkeys(DATASETS, True),
                "completion": completion,
                "glue_job_run_id": "jr_test",
                "glue_execution_time_seconds": 12,
                "glue_dpu_seconds": 24.0,
            }
        )
    )
    (directory / "dbt-summary.json").write_text(
        json.dumps({"nodes_passed": 152, "elapsed_seconds": 82.5})
    )
    (directory / "run-summary.json").write_text(
        json.dumps(
            {
                "airflow_run_id": airflow_run_id,
                "status": "success",
                "started_at": "2026-09-10T12:00:00+00:00",
                "finished_at": "2026-09-10T12:03:00+00:00",
            }
        )
    )
    return directory


def test_unified_run_report_aggregates_all_tiers_and_uploads_immutably(tmp_path):
    directory = write_run(tmp_path)
    assert locate_run_directory(tmp_path) == directory
    report = build_run_report(directory)
    assert report["status"] == "success"
    assert report["dbt_nodes_passed"] == 152
    assert report["component_durations_seconds"]["airflow_total"] == 180
    assert report["component_durations_seconds"]["glue_total"] == 12
    assert report["physical_runs"][0]["landing_ready"] is True
    assert report["physical_runs"][0]["records_extracted"] == 12
    assert set(report["physical_runs"][0]["records_curated_by_dataset"]) == set(DATASETS)
    target = persist_run_report(directory, report)
    assert json.loads(target.read_text())["schema_version"] == 1

    s3 = MagicMock()
    uri = upload_run_report(report, "bucket", s3_client=s3)
    assert uri == f"s3://bucket/metadata/pipeline_runs/{directory.name}.json"
    assert s3.put_object.call_args.kwargs["IfNoneMatch"] == "*"


def test_run_report_schema_rejects_incomplete_payload(tmp_path):
    directory = write_run(tmp_path)
    report = build_run_report(directory)
    report["physical_runs"][0]["records_loaded_by_dataset"].pop("tracks")
    with pytest.raises(ValueError, match="Landing datasets"):
        validate_run_report(report)
    with pytest.raises(FileNotFoundError):
        locate_run_directory(tmp_path, run_key_value="missing")


def test_replay_cli_defaults_to_safe_dry_run(monkeypatch, capsys):
    replay = load_script("replay_partition")
    assert replay.main(["--date", "2026-09-10", "--entity", "playlist_tracks"]) == 0
    output = capsys.readouterr().out
    assert "mode=dry-run" in output
    assert '"start_date":"2026-09-10"' in output
    assert "spotify_daily_snapshot" in output

    run = MagicMock()
    monkeypatch.setattr(replay.subprocess, "run", run)
    assert replay.main(["--date", "2026-09-10", "--execute"]) == 0
    run.assert_called_once()
    assert run.call_args.kwargs["check"] is True


def test_landing_lag_cli_uses_bounded_read_only_queries(capsys):
    audit = load_script("audit_landing_lag")
    sql = audit.copy_history_sql("LANDING_TRACKS", 24)
    assert "COPY_HISTORY" in sql
    assert "LANDING.LANDING_TRACKS" in sql
    assert "DELETE" not in sql.upper()
    assert audit.main(["--hours", "24", "--dry-run"]) == 0
    output = capsys.readouterr().out
    assert output.count("COPY_HISTORY") == len(audit.TABLES)
    with pytest.raises(ValueError):
        audit.copy_history_sql("OTHER", 24)
    with pytest.raises(ValueError):
        audit.copy_history_sql("LANDING_TRACKS", 999)
