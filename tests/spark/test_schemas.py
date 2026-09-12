"""Explicit Bronze and Silver schema contracts for Glue 5.1 / Spark 3.5.6."""

import json
from pathlib import Path

from pyspark.sql.types import BooleanType, DateType, IntegerType, StringType, TimestampType

from glue.schemas.bronze_schema import BRONZE_PLAYLIST_SNAPSHOT_SCHEMA
from glue.schemas.silver_schemas import SILVER_SCHEMAS

FIXTURES = Path(__file__).parents[1] / "fixtures" / "spotify"


def _bronze_fixture(tmp_path):
    playlist = json.loads((FIXTURES / "sample_playlist_response.json").read_text())
    page = json.loads((FIXTURES / "sample_playlist_items_single_page.json").read_text())
    payload = {
        "playlist_id": playlist["id"],
        "spotify_snapshot_id": playlist["snapshot_id"],
        "playlist": playlist,
        "pages": [page],
        "items": page["items"],
        "future_source_field": {"preserved_in_bronze": True},
    }
    path = tmp_path / "bronze.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_bronze_fixture_parses_with_explicit_schema_without_inference(spark, tmp_path):
    path = _bronze_fixture(tmp_path)
    frame = (
        spark.read.option("multiLine", True)
        .option("mode", "PERMISSIVE")
        .schema(BRONZE_PLAYLIST_SNAPSHOT_SCHEMA)
        .json(str(path))
    )

    row = frame.first()
    assert row is not None
    assert row.playlist_id == "6666666666666666666666"
    assert row.spotify_snapshot_id == "synthetic-snapshot-v1"
    assert row.playlist.name == "Synthetic Playlist"
    assert len(row.items) == 4
    assert row.items[0].item.album.release_date == "2026-01-01"
    assert row.items[0].item.artists[1].name == "Synthetic Artist 2"
    assert row._corrupt_record is None


def test_silver_schemas_match_documented_scalar_types_and_nullability():
    artists = {field.name: field for field in SILVER_SCHEMAS["artists"]}
    albums = {field.name: field for field in SILVER_SCHEMAS["albums"]}
    tracks = {field.name: field for field in SILVER_SCHEMAS["tracks"]}
    snapshots = {field.name: field for field in SILVER_SCHEMAS["playlist_snapshots"]}

    assert (
        isinstance(artists["artist_id"].dataType, StringType) and not artists["artist_id"].nullable
    )
    assert (
        isinstance(albums["total_tracks"].dataType, IntegerType) and albums["total_tracks"].nullable
    )
    assert (
        isinstance(tracks["is_explicit"].dataType, BooleanType)
        and not tracks["is_explicit"].nullable
    )
    assert isinstance(tracks["ingestion_date"].dataType, DateType)
    assert (
        isinstance(snapshots["added_at"].dataType, TimestampType) and snapshots["added_at"].nullable
    )
    assert isinstance(snapshots["snapshot_timestamp"].dataType, TimestampType)
