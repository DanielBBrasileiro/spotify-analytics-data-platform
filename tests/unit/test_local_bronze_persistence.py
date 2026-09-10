"""Immutable local Bronze writer contracts."""

import copy
import json
from datetime import UTC, date, datetime
from unittest.mock import patch
from uuid import UUID

import pytest

from spotify_data_platform.ingestion import (
    LocalBronzePersistenceError,
    LocalBronzeWriter,
    PipelineRunMetadata,
    RunStatus,
)
from spotify_data_platform.storage import build_bronze_playlist_key

RUN_ID = UUID("123e4567-e89b-42d3-a456-426614174000")
OTHER_RUN_ID = UUID("123e4567-e89b-42d3-a456-426614174001")
PLAYLIST_ID = "a" * 22


def metadata(**changes):
    values = {
        "pipeline_run_id": RUN_ID,
        "spotify_snapshot_id": "snapshot-v1",
        "playlist_id": PLAYLIST_ID,
        "snapshot_date": date(2026, 9, 1),
        "snapshot_timestamp": datetime(2026, 9, 9, 23, 30, 45, tzinfo=UTC),
        "records_extracted": 4,
        "status": RunStatus.SUCCESS,
    }
    values.update(changes)
    return PipelineRunMetadata(**values)


def snapshot():
    return {
        "playlist_id": PLAYLIST_ID,
        "spotify_snapshot_id": "snapshot-v1",
        "playlist": {
            "id": PLAYLIST_ID,
            "name": "Seleção sintética 🎵",
            "snapshot_id": "snapshot-v1",
            "future_field": {"preserve": True},
        },
        "pages": [
            {
                "offset": 0,
                "limit": 50,
                "total": 4,
                "next": None,
                "items": [None, {"item": None}, {"item": {"type": "episode"}}, {"item": None}],
            }
        ],
        "items": [None, {"item": None}, {"item": {"type": "episode"}}, {"item": None}],
    }


def test_destination_uses_capture_date_not_business_date(tmp_path):
    writer = LocalBronzeWriter(tmp_path)
    destination = writer.destination_for(metadata())
    assert destination == (
        tmp_path
        / "bronze"
        / "spotify"
        / "playlist_tracks"
        / "ingestion_date=2026-09-09"
        / f"run_id={RUN_ID}"
        / f"playlist_{PLAYLIST_ID}.json"
    )
    assert "ingestion_date=2026-09-01" not in str(destination)


def test_local_destination_reuses_canonical_s3_key_contract(tmp_path):
    run = metadata()
    expected_key = build_bronze_playlist_key(
        ingestion_date=run.snapshot_timestamp.date(),
        pipeline_run_id=run.pipeline_run_id,
        playlist_id=run.playlist_id,
    )
    assert LocalBronzeWriter(tmp_path).destination_for(run) == tmp_path / expected_key


def test_write_preserves_snapshot_values_and_does_not_inject_telemetry(tmp_path):
    raw = snapshot()
    original = copy.deepcopy(raw)
    destination = LocalBronzeWriter(tmp_path).write(raw, metadata())
    assert json.loads(destination.read_text(encoding="utf-8")) == original
    assert raw == original
    persisted = json.loads(destination.read_text(encoding="utf-8"))
    assert "pipeline_run_id" not in persisted
    assert "snapshot_date" not in persisted
    assert "status" not in persisted
    assert "🎵" in destination.read_text(encoding="utf-8")
    assert not list(destination.parent.glob("*.tmp"))


def test_existing_snapshot_is_never_overwritten(tmp_path):
    writer = LocalBronzeWriter(tmp_path)
    destination = writer.write(snapshot(), metadata())
    original_bytes = destination.read_bytes()
    with pytest.raises(LocalBronzePersistenceError, match="never overwritten"):
        writer.write(snapshot(), metadata())
    assert destination.read_bytes() == original_bytes
    assert not list(destination.parent.glob("*.tmp"))


def test_retry_with_new_physical_run_id_gets_separate_path(tmp_path):
    writer = LocalBronzeWriter(tmp_path)
    first = writer.write(snapshot(), metadata())
    second = writer.write(snapshot(), metadata(pipeline_run_id=OTHER_RUN_ID))
    assert first != second
    assert first.exists() and second.exists()
    assert json.loads(first.read_text()) == json.loads(second.read_text())


@pytest.mark.parametrize("status", [RunStatus.RUNNING, RunStatus.FAILED, RunStatus.PARTIAL])
def test_only_complete_success_snapshots_are_landable(tmp_path, status):
    writer = LocalBronzeWriter(tmp_path)
    with pytest.raises(LocalBronzePersistenceError, match="SUCCESS"):
        writer.write(snapshot(), metadata(status=status))
    assert not tmp_path.exists() or not any(tmp_path.rglob("*.json"))


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"playlist_id": "b" * 22}, "playlist_id"),
        ({"spotify_snapshot_id": "other-version"}, "spotify_snapshot_id"),
        ({"items": "not-an-array"}, "items must be an array"),
        ({"playlist": None}, "extraction envelope"),
        ({"pages": {}}, "extraction envelope"),
    ],
)
def test_snapshot_envelope_and_lineage_are_validated(tmp_path, change, message):
    raw = snapshot()
    raw.update(change)
    with pytest.raises(LocalBronzePersistenceError, match=message):
        LocalBronzeWriter(tmp_path).write(raw, metadata())


def test_record_count_must_match_raw_item_count(tmp_path):
    with pytest.raises(LocalBronzePersistenceError, match="records_extracted"):
        LocalBronzeWriter(tmp_path).write(snapshot(), metadata(records_extracted=3))


def test_unserializable_snapshot_creates_no_final_or_temp_file(tmp_path):
    raw = snapshot()
    raw["future_unserializable"] = object()
    writer = LocalBronzeWriter(tmp_path)
    final = writer.destination_for(metadata())
    with pytest.raises(LocalBronzePersistenceError, match="not JSON serializable"):
        writer.write(raw, metadata())
    assert not final.exists()
    assert not final.parent.exists()


def test_publish_failure_is_wrapped_and_temporary_file_is_cleaned(tmp_path):
    writer = LocalBronzeWriter(tmp_path)
    final = writer.destination_for(metadata())
    with (
        patch("spotify_data_platform.ingestion.persistence.os.link", side_effect=OSError("disk")),
        pytest.raises(LocalBronzePersistenceError, match="Could not publish"),
    ):
        writer.write(snapshot(), metadata())
    assert not final.exists()
    assert not list(final.parent.glob("*.tmp"))
