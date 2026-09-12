"""Historical playlist snapshot normalization contracts."""

from datetime import UTC, date, datetime
from uuid import UUID

import pytest

from glue.transforms.snapshots import SnapshotLineage, extract_playlist_snapshots
from tests.spark.helpers import bronze_frame, load_fixture

RUN_ID = UUID("123e4567-e89b-42d3-a456-426614174000")


def lineage():
    return SnapshotLineage(
        pipeline_run_id=RUN_ID,
        snapshot_date=date(2026, 9, 11),
        snapshot_timestamp=datetime(2026, 9, 12, 2, 30, 45, tzinfo=UTC),
        ingestion_date=date(2026, 9, 12),
    )


def test_snapshot_lineage_requires_uuid4_and_timezone_aware_timestamp():
    with pytest.raises(ValueError, match="UUID v4"):
        SnapshotLineage(
            pipeline_run_id=UUID("00000000-0000-1000-8000-000000000000"),
            snapshot_date=date(2026, 9, 11),
            snapshot_timestamp=datetime(2026, 9, 12, 2, 30, tzinfo=UTC),
            ingestion_date=date(2026, 9, 12),
        )
    with pytest.raises(ValueError, match="timezone-aware"):
        SnapshotLineage(
            pipeline_run_id=RUN_ID,
            snapshot_date=date(2026, 9, 11),
            snapshot_timestamp=datetime(2026, 9, 12, 2, 30),
            ingestion_date=date(2026, 9, 12),
        )


def test_extract_playlist_snapshots_preserves_source_position_and_lineage(spark):
    rows = extract_playlist_snapshots(bronze_frame(spark), lineage=lineage()).collect()

    assert len(rows) == 1
    row = rows[0]
    assert row.playlist_id == "6666666666666666666666"
    assert row.spotify_snapshot_id == "synthetic-snapshot-v1"
    assert row.playlist_name == "Synthetic Playlist"
    assert row.track_id == "0000000000000000000101"
    assert row.track_position == 0
    assert row.added_at is None
    assert row.snapshot_date.isoformat() == "2026-09-11"
    assert row.snapshot_timestamp == datetime(2026, 9, 12, 2, 30, 45)
    assert row.pipeline_run_id == str(RUN_ID)
    assert row.ingestion_date.isoformat() == "2026-09-12"


def test_same_track_in_multiple_positions_remains_multiple_snapshot_slots(spark):
    item = load_fixture("sample_playlist_items_single_page.json")["items"][0]
    rows = (
        extract_playlist_snapshots(bronze_frame(spark, items=[item, item]), lineage=lineage())
        .orderBy("track_position")
        .collect()
    )

    assert [(row.track_id, row.track_position) for row in rows] == [
        ("0000000000000000000101", 0),
        ("0000000000000000000101", 1),
    ]


def test_invalid_items_create_position_gaps_instead_of_reindexing(spark):
    items = load_fixture("sample_playlist_items_single_page.json")["items"]
    valid = items[0]
    rows = (
        extract_playlist_snapshots(
            bronze_frame(spark, items=[items[2], valid, items[3], valid]), lineage=lineage()
        )
        .orderBy("track_position")
        .collect()
    )
    assert [row.track_position for row in rows] == [1, 3]
