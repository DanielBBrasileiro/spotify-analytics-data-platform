"""Aggregate immutable Airflow/Glue/Landing/dbt evidence into one run manifest."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from spotify_data_platform.orchestration.contracts import DATASETS, run_key

SCHEMA_VERSION = 1


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def _iso_duration_seconds(started_at: str | None, finished_at: str | None) -> float | None:
    if not started_at or not finished_at:
        return None
    try:
        start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        finish = datetime.fromisoformat(finished_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    return max(0.0, (finish - start).total_seconds())


def locate_run_directory(
    artifact_root: str | Path,
    *,
    airflow_run_id: str | None = None,
    run_key_value: str | None = None,
) -> Path:
    """Locate one persisted Airflow run; latest completed run is the safe default."""
    root = Path(artifact_root)
    if airflow_run_id and run_key_value:
        raise ValueError("Pass airflow_run_id or run_key_value, not both.")
    if airflow_run_id:
        candidate = root / run_key(airflow_run_id)
        if not candidate.is_dir():
            raise FileNotFoundError(f"No artifacts for Airflow run {airflow_run_id}.")
        return candidate
    if run_key_value:
        candidate = root / run_key_value
        if not candidate.is_dir():
            raise FileNotFoundError(f"No artifact directory {run_key_value}.")
        return candidate
    completed = [p for p in root.iterdir() if p.is_dir() and (p / "run-summary.json").is_file()]
    if not completed:
        raise FileNotFoundError(f"No completed run artifacts under {root}.")
    return max(completed, key=lambda p: (p / "run-summary.json").stat().st_mtime)


def build_run_report(run_directory: str | Path) -> dict[str, Any]:
    """Build one schema-validated report from the evidence files of a DAG run."""
    directory = Path(run_directory)
    plan = _read_json(directory / "plan.json")
    summary = _read_json(directory / "run-summary.json")
    dbt = (
        _read_json(directory / "dbt-summary.json")
        if (directory / "dbt-summary.json").is_file()
        else None
    )
    planned_by_pipeline = {
        record["pipeline_run_id"]: record
        for record in plan.get("records", [])
        if isinstance(record, dict) and record.get("pipeline_run_id")
    }

    glue_by_pipeline: dict[str, dict[str, Any]] = {}
    for path in sorted(directory.glob("glue-*.json")):
        payload = _read_json(path)
        record = payload["record"]
        glue_by_pipeline[record["pipeline_run_id"]] = payload

    physical_runs = []
    for path in sorted(directory.glob("landing-*.json")):
        payload = _read_json(path)
        completion = payload["completion"]
        pipeline_run_id = completion["pipeline_run_id"]
        glue = glue_by_pipeline.get(pipeline_run_id, {})
        expected_rows = {
            dataset: sum(int(file_info["rows"]) for file_info in completion["datasets"][dataset])
            for dataset in DATASETS
        }
        loaded_rows = {
            dataset: expected_rows[dataset] if payload["datasets"].get(dataset) else None
            for dataset in DATASETS
        }
        record = glue.get("record", {})
        planned_record = planned_by_pipeline.get(pipeline_run_id, {})
        records_extracted = record.get("records_extracted", planned_record.get("records_extracted"))
        if records_extracted is None and planned_record.get("local_path"):
            source_path = Path(planned_record["local_path"])
            if source_path.is_file():
                source_items = _read_json(source_path).get("items")
                if isinstance(source_items, list):
                    records_extracted = len(source_items)
        physical_runs.append(
            {
                "pipeline_run_id": pipeline_run_id,
                "spotify_snapshot_id": record.get("spotify_snapshot_id"),
                "snapshot_date": completion["snapshot_date"],
                "playlist_id": completion["playlist_id"],
                "records_extracted": records_extracted,
                "glue_job_run_id": payload.get("glue_job_run_id") or glue.get("job_run_id"),
                "glue_execution_time_seconds": payload.get("glue_execution_time_seconds"),
                "glue_dpu_seconds": payload.get("glue_dpu_seconds"),
                "landing_ready": bool(payload["ready"]),
                "rejected_items": int(completion["rejected_items"]),
                "records_curated_by_dataset": expected_rows,
                "records_loaded_by_dataset": loaded_rows,
            }
        )

    glue_seconds = [
        item["glue_execution_time_seconds"]
        for item in physical_runs
        if isinstance(item.get("glue_execution_time_seconds"), (int, float))
    ]
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "run_key": directory.name,
        "airflow_run_id": summary["airflow_run_id"],
        "status": summary["status"],
        "source_type": plan.get("source_type"),
        "temporal_state": plan.get("temporal_state"),
        "start_date": plan["start_date"],
        "end_date": plan["end_date"],
        "component_durations_seconds": {
            "airflow_total": _iso_duration_seconds(
                summary.get("started_at"), summary.get("finished_at")
            ),
            "glue_total": sum(glue_seconds) if glue_seconds else None,
            "dbt": dbt.get("elapsed_seconds") if dbt else None,
        },
        "dbt_nodes_passed": dbt.get("nodes_passed") if dbt else None,
        "physical_runs": physical_runs,
    }
    validate_run_report(report)
    return report


def validate_run_report(report: dict[str, Any]) -> None:
    """Strict lightweight schema guard used both by CLI and tests."""
    required = {
        "schema_version",
        "generated_at",
        "run_key",
        "airflow_run_id",
        "status",
        "start_date",
        "end_date",
        "component_durations_seconds",
        "physical_runs",
    }
    missing = required - report.keys()
    if missing:
        raise ValueError(f"Run report missing fields: {sorted(missing)}")
    if report["schema_version"] != SCHEMA_VERSION:
        raise ValueError("Unsupported run report schema version.")
    if report["status"] not in {"success", "failed"}:
        raise ValueError("Run report status must be success or failed.")
    if not isinstance(report["physical_runs"], list):
        raise ValueError("physical_runs must be a list.")
    for item in report["physical_runs"]:
        if set(item["records_curated_by_dataset"]) != set(DATASETS):
            raise ValueError("Run report must include all curated datasets.")
        if set(item["records_loaded_by_dataset"]) != set(DATASETS):
            raise ValueError("Run report must include all Landing datasets.")


def persist_run_report(run_directory: str | Path, report: dict[str, Any]) -> Path:
    """Persist atomically next to the source evidence."""
    validate_run_report(report)
    target = Path(run_directory) / "pipeline-run-report.json"
    pending = target.with_suffix(".json.tmp")
    pending.write_text(json.dumps(report, indent=2, default=str) + "\n")
    pending.replace(target)
    return target


def upload_run_report(report: dict[str, Any], bucket: str, *, s3_client=None) -> str:
    """Publish immutable cross-tier evidence under metadata/pipeline_runs/."""
    validate_run_report(report)
    if s3_client is None:
        import boto3

        s3_client = boto3.client("s3")
    key = f"metadata/pipeline_runs/{report['run_key']}.json"
    s3_client.put_object(
        Bucket=bucket,
        Key=key,
        Body=(json.dumps(report, indent=2, default=str) + "\n").encode(),
        ContentType="application/json",
        IfNoneMatch="*",
    )
    return f"s3://{bucket}/{key}"
