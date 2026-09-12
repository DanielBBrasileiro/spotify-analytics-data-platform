"""High-value regression guards spanning the complete M3 Silver contract."""

import socket
from pathlib import Path

import pytest

from glue.jobs.bronze_to_silver_curation import read_bronze_snapshot
from glue.schemas.bronze_schema import BRONZE_PLAYLIST_SNAPSHOT_SCHEMA
from glue.schemas.silver_schemas import SILVER_SCHEMAS
from glue.schemas.validation import SchemaContractError
from glue.transforms.snapshots import SNAPSHOT_NATURAL_KEY


def _field_names(schema):
    names = set()
    for field in schema.fields:
        names.add(field.name)
        data_type = field.dataType
        if hasattr(data_type, "fields"):
            names.update(_field_names(data_type))
        elif hasattr(data_type, "elementType") and hasattr(data_type.elementType, "fields"):
            names.update(_field_names(data_type.elementType))
    return names


def test_malformed_bronze_json_is_rejected_without_echoing_payload(spark, tmp_path):
    sensitive = '{"playlist_id":"secret", broken-json'
    path = tmp_path / "malformed.json"
    path.write_text(sensitive, encoding="utf-8")

    with pytest.raises(SchemaContractError) as error:
        read_bronze_snapshot(spark, path)
    assert "corrupt records" in str(error.value)
    assert "secret" not in str(error.value)


def test_external_network_remains_blocked_during_spark_tests():
    with pytest.raises(AssertionError, match="Network access is forbidden"):
        socket.getaddrinfo("example.com", 443)


def test_deprecated_popularity_and_record_label_fields_are_absent_from_m3_contracts():
    bronze_names = _field_names(BRONZE_PLAYLIST_SNAPSHOT_SCHEMA)
    silver_names = set().union(*(_field_names(schema) for schema in SILVER_SCHEMAS.values()))
    assert "popularity" not in bronze_names | silver_names
    assert "label" not in bronze_names | silver_names


def test_snapshot_natural_key_excludes_physical_execution_timestamp():
    assert SNAPSHOT_NATURAL_KEY == ("playlist_id", "snapshot_date", "track_position")
    assert "snapshot_timestamp" not in SNAPSHOT_NATURAL_KEY
    assert "pipeline_run_id" not in SNAPSHOT_NATURAL_KEY


def test_silver_schema_column_order_is_stable_for_landing_contract():
    assert [field.name for field in SILVER_SCHEMAS["artists"].fields] == [
        "artist_id",
        "artist_name",
        "ingestion_date",
    ]
    assert [field.name for field in SILVER_SCHEMAS["playlist_snapshots"].fields] == [
        "playlist_id",
        "spotify_snapshot_id",
        "playlist_name",
        "track_id",
        "track_position",
        "added_at",
        "snapshot_date",
        "snapshot_timestamp",
        "pipeline_run_id",
        "ingestion_date",
    ]


def test_no_spark_test_fixture_accidentally_points_at_a_live_data_path():
    fixture_root = Path(__file__).parents[1] / "fixtures" / "spotify"
    assert fixture_root.is_dir()
    representative = (
        fixture_root / "sample_playlist_response.json",
        fixture_root / "sample_playlist_items_single_page.json",
        fixture_root / "sample_multi_artist_track.json",
    )
    assert all("synthetic" in path.read_text(encoding="utf-8").lower() for path in representative)
