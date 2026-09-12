"""Deterministic deduplication and sanitized item quarantine contracts."""

from datetime import date, datetime

from pyspark.sql.types import (
    DateType,
    IntegerType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

from glue.transforms.dedup import deterministic_dedupe
from glue.transforms.quarantine import rejected_playlist_items
from glue.transforms.snapshots import deduplicate_playlist_snapshots
from tests.spark.helpers import bronze_frame


def test_entity_deduplication_is_deterministic_for_conflicting_rows(spark):
    frame = spark.createDataFrame(
        [("artist-1", "Zed"), ("artist-1", "Alpha"), ("artist-2", "Beta")],
        ["artist_id", "artist_name"],
    )
    first = (
        deterministic_dedupe(
            frame,
            keys=("artist_id",),
            ordering=(frame.artist_name.asc(),),
        )
        .orderBy("artist_id")
        .collect()
    )
    second = (
        deterministic_dedupe(
            frame.repartition(2),
            keys=("artist_id",),
            ordering=(frame.artist_name.asc(),),
        )
        .orderBy("artist_id")
        .collect()
    )
    assert [(row.artist_id, row.artist_name) for row in first] == [
        ("artist-1", "Alpha"),
        ("artist-2", "Beta"),
    ]
    assert first == second


def test_snapshot_dedup_prefers_latest_execution_without_using_timestamp_in_key(spark):
    schema = StructType(
        [
            StructField("playlist_id", StringType(), False),
            StructField("track_id", StringType(), False),
            StructField("snapshot_date", DateType(), False),
            StructField("track_position", IntegerType(), False),
            StructField("snapshot_timestamp", TimestampType(), False),
            StructField("pipeline_run_id", StringType(), False),
        ]
    )
    frame = spark.createDataFrame(
        [
            ("p", "old-track", date(2026, 9, 12), 0, datetime(2026, 9, 12, 1), "run-a"),
            ("p", "new-track", date(2026, 9, 12), 0, datetime(2026, 9, 12, 2), "run-b"),
        ],
        schema,
    )
    rows = deduplicate_playlist_snapshots(frame).collect()
    assert [(row.track_id, row.pipeline_run_id) for row in rows] == [("new-track", "run-b")]


def test_quarantine_classifies_episode_local_and_unavailable_without_raw_payload(spark):
    rows = rejected_playlist_items(bronze_frame(spark)).orderBy("track_position").collect()
    assert [(row.track_position, row.rejection_reason) for row in rows] == [
        (1, "LOCAL_TRACK_WITHOUT_ID"),
        (2, "UNSUPPORTED_ITEM_TYPE"),
        (3, "UNAVAILABLE_ITEM"),
    ]
    assert rejected_playlist_items(bronze_frame(spark)).columns == [
        "playlist_id",
        "spotify_snapshot_id",
        "track_position",
        "item_type",
        "is_local",
        "rejection_reason",
    ]


def test_dedupe_requires_present_nonempty_key_list(spark):
    frame = spark.createDataFrame([("a",)], ["value"])
    try:
        deterministic_dedupe(frame, keys=())
    except ValueError as exc:
        assert "At least one" in str(exc)
    else:
        raise AssertionError("missing key contract should fail")

    try:
        deterministic_dedupe(frame, keys=("missing",))
    except ValueError as exc:
        assert "missing" in str(exc)
    else:
        raise AssertionError("unknown key should fail")
