"""Artist normalization contracts."""

from datetime import date

from glue.transforms.entities import extract_artists
from tests.spark.helpers import bronze_frame, load_fixture


def test_extract_artists_keeps_valid_credited_entities_and_excludes_local_null_ids(spark):
    rows = (
        extract_artists(bronze_frame(spark), ingestion_date=date(2026, 9, 12))
        .orderBy("artist_id")
        .collect()
    )

    assert [(row.artist_id, row.artist_name) for row in rows] == [
        ("0000000000000000000001", "Synthetic Artist 1"),
        ("0000000000000000000002", "Synthetic Artist 2"),
    ]
    assert {row.ingestion_date.isoformat() for row in rows} == {"2026-09-12"}


def test_extract_artists_deduplicates_repeated_provider_artist_id(spark):
    item = load_fixture("sample_playlist_items_single_page.json")["items"][0]
    rows = extract_artists(
        bronze_frame(spark, items=[item, item]), ingestion_date="2026-09-12"
    ).collect()
    assert {row.artist_id for row in rows} == {
        "0000000000000000000001",
        "0000000000000000000002",
    }
    assert len(rows) == 2
