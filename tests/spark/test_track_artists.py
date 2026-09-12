"""Track/artist bridge normalization contracts."""

import copy

from glue.transforms.entities import extract_track_artists
from tests.spark.helpers import bronze_frame, load_fixture


def test_extract_track_artists_preserves_multi_artist_billing_order(spark):
    rows = (
        extract_track_artists(bronze_frame(spark), ingestion_date="2026-09-12")
        .orderBy("artist_order")
        .collect()
    )

    assert [(row.artist_id, row.artist_order) for row in rows] == [
        ("0000000000000000000001", 0),
        ("0000000000000000000002", 1),
    ]
    assert {row.track_id for row in rows} == {"0000000000000000000101"}


def test_extract_track_artists_preserves_source_position_when_null_artist_is_skipped(spark):
    item = copy.deepcopy(load_fixture("sample_playlist_items_single_page.json")["items"][0])
    item["item"]["artists"][0]["id"] = None
    rows = extract_track_artists(
        bronze_frame(spark, items=[item]), ingestion_date="2026-09-12"
    ).collect()
    assert [(row.artist_id, row.artist_order) for row in rows] == [("0000000000000000000002", 1)]


def test_extract_track_artists_deduplicates_exact_bridge_records(spark):
    item = load_fixture("sample_playlist_items_single_page.json")["items"][0]
    rows = extract_track_artists(
        bronze_frame(spark, items=[item, item]), ingestion_date="2026-09-12"
    ).collect()
    assert len(rows) == 2
