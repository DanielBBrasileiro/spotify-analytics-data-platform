"""Album normalization contracts."""

import copy
from datetime import date

from glue.transforms.entities import extract_albums
from tests.spark.helpers import bronze_frame, load_fixture


def test_extract_albums_keeps_documented_fields_and_excludes_local_null_album(spark):
    rows = extract_albums(bronze_frame(spark), ingestion_date=date(2026, 9, 12)).collect()

    assert len(rows) == 1
    row = rows[0]
    assert row.album_id == "9999999999999999999999"
    assert row.album_name == "Synthetic Test Album"
    assert row.album_type == "album"
    assert row.release_date == "2026-01-01"
    assert row.total_tracks == 52
    assert row.ingestion_date.isoformat() == "2026-09-12"


def test_extract_albums_preserves_year_only_release_date_string(spark):
    item = copy.deepcopy(load_fixture("sample_playlist_items_single_page.json")["items"][0])
    item["item"]["album"]["release_date"] = "2021"
    rows = extract_albums(bronze_frame(spark, items=[item]), ingestion_date="2026-09-12").collect()
    assert rows[0].release_date == "2021"


def test_extract_albums_deduplicates_repeated_album_id(spark):
    item = load_fixture("sample_playlist_items_single_page.json")["items"][0]
    rows = extract_albums(
        bronze_frame(spark, items=[item, item]), ingestion_date="2026-09-12"
    ).collect()
    assert len(rows) == 1
