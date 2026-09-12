"""End-to-end synthetic Bronze-to-Silver local Spark pipeline tests."""

import json
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import UUID

import pytest

from glue.jobs.bronze_to_silver_curation import (
    build_silver_datasets,
    read_bronze_snapshot,
    run_bronze_to_silver,
)
from glue.schemas.bronze_schema import BRONZE_PLAYLIST_SNAPSHOT_SCHEMA
from glue.schemas.validation import SchemaContractError
from glue.transforms.snapshots import SnapshotLineage
from tests.spark.helpers import bronze_payload, load_fixture

RUN_ID = UUID("123e4567-e89b-42d3-a456-426614174000")


def _lineage():
    return SnapshotLineage(
        pipeline_run_id=RUN_ID,
        snapshot_date=date(2026, 9, 11),
        snapshot_timestamp=datetime(2026, 9, 12, 2, 30, 45, tzinfo=UTC),
        ingestion_date=date(2026, 9, 12),
    )


def _write_bronze(path: Path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def test_end_to_end_single_page_writes_all_six_silver_datasets(spark, tmp_path):
    bronze_path = _write_bronze(tmp_path / "bronze.json", bronze_payload())
    output_root = tmp_path / "lake"

    result = run_bronze_to_silver(
        spark,
        bronze_path=bronze_path,
        silver_root=output_root,
        lineage=_lineage(),
    )

    assert result.rejected_items == 3
    assert set(result.destinations) == {
        "artists",
        "albums",
        "tracks",
        "track_artists",
        "playlist_snapshots",
        "playlist_observations",
    }
    expected_counts = {
        "artists": 2,
        "albums": 1,
        "tracks": 1,
        "track_artists": 2,
        "playlist_snapshots": 1,
        "playlist_observations": 1,
    }
    for dataset, expected in expected_counts.items():
        destination = Path(result.destinations[dataset])
        assert destination.relative_to(output_root).as_posix() == (
            f"silver/{dataset}/ingestion_date=2026-09-12/"
            f"run_id={RUN_ID}/playlist_id=6666666666666666666666"
        )
        assert spark.read.parquet(str(destination)).count() == expected


def test_consolidated_items_are_transformed_once_even_when_pages_duplicate_them(spark, tmp_path):
    playlist = load_fixture("sample_playlist_response.json")
    first = load_fixture("sample_playlist_items_response.json")
    last = load_fixture("sample_playlist_items_last_page.json")
    items = first["items"] + last["items"]
    payload = {
        "playlist_id": playlist["id"],
        "spotify_snapshot_id": playlist["snapshot_id"],
        "playlist": playlist,
        "pages": [first, last],
        "items": items,
    }
    path = _write_bronze(tmp_path / "bronze-52.json", payload)
    bronze = read_bronze_snapshot(spark, path)
    datasets, rejected = build_silver_datasets(bronze, lineage=_lineage())

    assert len(items) == 52
    assert datasets["playlist_snapshots"].count() == 52
    assert datasets["tracks"].count() == 52
    assert rejected.count() == 0


def test_future_unknown_bronze_fields_do_not_break_explicit_schema(spark, tmp_path):
    payload = bronze_payload()
    payload["future_source_field"] = {"new": [1, 2, 3]}
    path = _write_bronze(tmp_path / "future.json", payload)
    frame = read_bronze_snapshot(spark, path)
    assert frame.count() == 1
    assert "future_source_field" not in frame.columns


def test_empty_playlist_still_emits_observation_without_snapshot_slots(spark):
    bronze = spark.createDataFrame(
        [bronze_payload(items=[])],
        schema=BRONZE_PLAYLIST_SNAPSHOT_SCHEMA,
    )
    datasets, rejected = build_silver_datasets(bronze, lineage=_lineage())
    assert datasets["playlist_snapshots"].count() == 0
    observation = datasets["playlist_observations"].first()
    assert observation is not None
    assert observation.source_item_count == 0
    assert observation.valid_track_count == 0
    assert observation.rejected_item_count == 0
    assert rejected.count() == 0


def test_curation_rejects_multiple_bronze_objects_for_one_lineage(spark, tmp_path):
    bronze_dir = tmp_path / "bronze"
    bronze_dir.mkdir()
    _write_bronze(bronze_dir / "run-a.json", bronze_payload())
    second = bronze_payload()
    second["spotify_snapshot_id"] = "synthetic-snapshot-v2"
    second["playlist"]["snapshot_id"] = "synthetic-snapshot-v2"
    _write_bronze(bronze_dir / "run-b.json", second)

    with pytest.raises(SchemaContractError, match="exactly one Bronze snapshot object"):
        read_bronze_snapshot(spark, bronze_dir)
