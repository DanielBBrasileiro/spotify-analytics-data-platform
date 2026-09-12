"""Track normalization contracts."""

import copy
from datetime import date

from glue.transforms.entities import extract_tracks
from tests.spark.helpers import bronze_frame, load_fixture


def test_extract_tracks_keeps_typed_track_metadata_and_rejects_non_tracks(spark):
    rows = extract_tracks(bronze_frame(spark), ingestion_date=date(2026, 9, 12)).collect()

    assert len(rows) == 1
    row = rows[0]
    assert row.track_id == "0000000000000000000101"
    assert row.track_name == "Synthetic Track 1"
    assert row.album_id == "9999999999999999999999"
    assert row.duration_ms == 180001
    assert row.is_explicit is False
    assert row.is_local is False
    assert row.ingestion_date.isoformat() == "2026-09-12"


def test_extract_tracks_deduplicates_provider_track_id(spark):
    item = load_fixture("sample_playlist_items_single_page.json")["items"][0]
    rows = extract_tracks(
        bronze_frame(spark, items=[item, item]), ingestion_date="2026-09-12"
    ).collect()
    assert len(rows) == 1


def test_extract_tracks_rejects_track_missing_required_silver_value(spark):
    item = copy.deepcopy(load_fixture("sample_playlist_items_single_page.json")["items"][0])
    item["item"]["duration_ms"] = None
    assert (
        extract_tracks(bronze_frame(spark, items=[item]), ingestion_date="2026-09-12").count() == 0
    )
