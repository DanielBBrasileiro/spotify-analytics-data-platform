"""Failure-oriented checks for physical replay and the pre-dbt completeness gate."""

import copy
import json
from uuid import UUID

import pytest

from spotify_data_platform.orchestration.contracts import (
    DATASETS,
    landing_ready,
    plan_demo,
    validate_completion,
)


@pytest.fixture
def manifest(tmp_path):
    source = {
        "playlist_id": "1" * 22,
        "spotify_snapshot_id": "cc0-sim-test",
        "source_provenance": {"temporal_state": "synthetic"},
    }
    (tmp_path / "bronze.json").write_text(json.dumps(source))
    doc = {
        "source": {"license": "CC0-1.0"},
        "records": [
            {
                "playlist_id": source["playlist_id"],
                "spotify_snapshot_id": source["spotify_snapshot_id"],
                "snapshot_date": "2026-09-10",
                "ingestion_date": "2026-09-10",
                "snapshot_timestamp": "2026-09-10T12:00:00+00:00",
                "bronze_relative_path": "bronze.json",
            }
        ],
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(doc))
    return path


def plan(path, run="manual-test", start="2026-09-10", end="2026-09-10"):
    return plan_demo(str(path), start, end, run)


def completion(record):
    result = {
        field: record[field]
        for field in ("pipeline_run_id", "playlist_id", "snapshot_date", "ingestion_date")
    }
    result.update(
        schema_version=1,
        rejected_items=0,
        datasets={
            dataset: [
                {
                    "key": f"silver/{dataset}/ingestion_date={record['ingestion_date']}/"
                    f"run_id={record['pipeline_run_id']}/playlist_id={record['playlist_id']}/part.parquet",
                    "rows": 1,
                }
            ]
            for dataset in DATASETS
        },
    )
    return result


def test_retry_stable_but_new_dag_run_gets_new_physical_publication(manifest):
    first = plan(manifest)
    assert first == plan(manifest)
    second = plan(manifest, run="replay")
    a, b = first["records"][0], second["records"][0]
    assert a["pipeline_run_id"] != b["pipeline_run_id"]
    assert a["sha256"] == b["sha256"]
    assert UUID(a["pipeline_run_id"]).version == 4
    assert a["bronze_key"] != b["bronze_key"]


@pytest.mark.parametrize(
    "start,end",
    [
        ("2026-09-11", "2026-09-10"),
        ("2026-09-10", "2026-11-10"),
        ("2026-09-10", "2026-09-11"),
        ("2026-09-01", "2026-09-01"),
    ],
)
def test_invalid_or_unavailable_windows_fail(manifest, start, end):
    with pytest.raises(ValueError):
        plan(manifest, start=start, end=end)


@pytest.mark.parametrize(
    "mutation", ["license", "duplicate", "escape", "playlist", "timestamp", "naive", "source"]
)
def test_invalid_demo_manifest_fails_before_cloud_io(manifest, mutation):
    doc = json.loads(manifest.read_text())
    row = doc["records"][0]
    if mutation == "license":
        doc["source"]["license"] = "unknown"
    elif mutation == "duplicate":
        doc["records"].append(copy.deepcopy(row))
    elif mutation == "escape":
        row["bronze_relative_path"] = "../other.json"
    elif mutation == "playlist":
        row["playlist_id"] = "../bad"
    elif mutation == "timestamp":
        row["snapshot_timestamp"] = "2026-09-11T12:00:00+00:00"
    elif mutation == "naive":
        row["snapshot_timestamp"] = "2026-09-10T12:00:00"
    else:
        row["spotify_snapshot_id"] = "wrong"
    manifest.write_text(json.dumps(doc))
    with pytest.raises(ValueError):
        plan(manifest)


def test_completion_requires_all_six_datasets_and_matching_run(manifest):
    record = plan(manifest)["records"][0]
    inventory = completion(record)
    assert len(validate_completion(inventory, record)) == 6
    del inventory["datasets"]["artists"]
    with pytest.raises(ValueError, match="six"):
        validate_completion(inventory, record)


@pytest.mark.parametrize(
    "mutation",
    ["version", "lineage", "empty", "path", "rows", "duplicate", "observation", "rejected"],
)
def test_invalid_inventory_fails_closed(manifest, mutation):
    record = plan(manifest)["records"][0]
    doc = completion(record)
    file = doc["datasets"]["tracks"][0]
    if mutation == "version":
        doc["schema_version"] = 2
    elif mutation == "lineage":
        doc["pipeline_run_id"] = "other-run"
    elif mutation == "empty":
        doc["datasets"]["tracks"] = []
    elif mutation == "path":
        file["key"] = "silver/tracks/other-run.parquet"
    elif mutation == "rows":
        file["rows"] = -1
    elif mutation == "duplicate":
        doc["datasets"]["tracks"].append(dict(file))
    elif mutation == "observation":
        doc["datasets"]["playlist_observations"][0]["rows"] = 0
    else:
        doc["rejected_items"] = -1
    with pytest.raises(ValueError):
        validate_completion(doc, record)


def test_gate_waits_for_last_file_and_rejects_duplicate_physical_rows():
    expected = [
        {"key": "silver/tracks/run/one.parquet", "rows": 2},
        {"key": "silver/tracks/run/two.parquet", "rows": 1},
    ]
    partial = [("tracks/run/one.parquet", 2, 2)]
    assert not landing_ready(expected, partial)
    assert landing_ready(expected, [*partial, ("silver/tracks/run/two.parquet", 1, 1)])
    with pytest.raises(ValueError, match="Duplicated"):
        landing_ready(expected, [("tracks/run/one.parquet", 2, 1)])
    with pytest.raises(ValueError, match="excess"):
        landing_ready(expected, [("tracks/run/one.parquet", 3, 3)])


def test_gate_empty_dataset_and_unexpected_files():
    expected = [{"key": "silver/tracks/run/empty.parquet", "rows": 0}]
    assert landing_ready(expected, [])
    with pytest.raises(ValueError, match="Unexpected"):
        landing_ready(expected, [("tracks/other-run/file.parquet", 1, 1)])
    expected[0]["rows"] = 1
    rows = [("tracks/run/empty.parquet", 1, 1)]
    with pytest.raises(ValueError, match="repeated"):
        landing_ready(expected, rows * 2)
