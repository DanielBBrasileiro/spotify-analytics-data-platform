"""Canonical S3 Bronze object-key and URI contracts."""

from datetime import date, datetime
from uuid import UUID, uuid1

import pytest

from spotify_data_platform.storage import (
    S3PathValidationError,
    build_bronze_playlist_key,
    build_bronze_playlist_uri,
)

RUN_ID = UUID("123e4567-e89b-42d3-a456-426614174000")
PLAYLIST_ID = "AbCdEf0123456789GhIjKl"


@pytest.mark.parametrize(
    ("ingestion_date", "expected_partition"),
    [
        (date(2026, 1, 2), "ingestion_date=2026-01-02"),
        (date(2026, 9, 9), "ingestion_date=2026-09-09"),
        (date(2028, 2, 29), "ingestion_date=2028-02-29"),
    ],
)
def test_bronze_key_uses_zero_padded_hive_partitions(ingestion_date, expected_partition):
    key = build_bronze_playlist_key(
        ingestion_date=ingestion_date,
        pipeline_run_id=RUN_ID,
        playlist_id=PLAYLIST_ID,
    )
    assert key == (
        "bronze/spotify/playlist_tracks/"
        f"{expected_partition}/run_id={RUN_ID}/playlist_{PLAYLIST_ID}.json"
    )


def test_bronze_uri_is_deterministic_and_contains_exact_key():
    key = build_bronze_playlist_key(
        ingestion_date=date(2026, 1, 2),
        pipeline_run_id=RUN_ID,
        playlist_id=PLAYLIST_ID,
    )
    uri = build_bronze_playlist_uri(
        "spotify-data-123",
        ingestion_date=date(2026, 1, 2),
        pipeline_run_id=RUN_ID,
        playlist_id=PLAYLIST_ID,
    )
    assert uri == f"s3://spotify-data-123/{key}"
    assert "//" not in key
    assert "/./" not in key
    assert "/../" not in key


@pytest.mark.parametrize(
    "bucket",
    [
        "spotify-data-123",
        "spotify.data.123",
        "a1b",
        "data-2026-portfolio",
        "portfolio-123456789012-us-east-1-an",
    ],
)
def test_valid_general_purpose_bucket_names_are_accepted(bucket):
    assert build_bronze_playlist_uri(
        bucket,
        ingestion_date=date(2026, 9, 9),
        pipeline_run_id=RUN_ID,
        playlist_id=PLAYLIST_ID,
    ).startswith(f"s3://{bucket}/")


@pytest.mark.parametrize(
    "bucket",
    [
        "",
        "ab",
        "A-Uppercase",
        "has_underscore",
        "has/slash",
        "../escape",
        "s3://nested",
        "-leading-hyphen",
        "trailing-hyphen-",
        ".leading-dot",
        "trailing-dot.",
        "adjacent..periods",
        "192.168.5.4",
        "xn--reserved",
        "sthree-reserved",
        "amzn-s3-demo-reserved",
        "reserved-s3alias",
        "reserved--ol-s3",
        "reserved.mrap",
        "reserved--x-s3",
        "reserved--table-s3",
        "a" * 64,
    ],
)
def test_invalid_or_reserved_bucket_names_are_rejected(bucket):
    with pytest.raises(S3PathValidationError):
        build_bronze_playlist_uri(
            bucket,
            ingestion_date=date(2026, 9, 9),
            pipeline_run_id=RUN_ID,
            playlist_id=PLAYLIST_ID,
        )


@pytest.mark.parametrize(
    "playlist_id",
    [
        "a" * 21,
        "a" * 23,
        "../" + "a" * 19,
        "a/b" + "c" * 19,
        "." * 22,
        "á" + "a" * 21,
    ],
)
def test_playlist_id_cannot_escape_or_change_key_shape(playlist_id):
    with pytest.raises(S3PathValidationError, match="playlist_id"):
        build_bronze_playlist_key(
            ingestion_date=date(2026, 9, 9),
            pipeline_run_id=RUN_ID,
            playlist_id=playlist_id,
        )


@pytest.mark.parametrize("run_id", [uuid1(), "123e4567-e89b-42d3-a456-426614174000", None])
def test_pipeline_run_id_must_be_uuid_v4(run_id):
    with pytest.raises(S3PathValidationError, match="UUID v4"):
        build_bronze_playlist_key(
            ingestion_date=date(2026, 9, 9),
            pipeline_run_id=run_id,
            playlist_id=PLAYLIST_ID,
        )


@pytest.mark.parametrize("ingestion_date", ["2026-09-09", datetime(2026, 9, 9), None])
def test_ingestion_date_requires_date_object(ingestion_date):
    with pytest.raises(S3PathValidationError, match="datetime.date"):
        build_bronze_playlist_key(
            ingestion_date=ingestion_date,
            pipeline_run_id=RUN_ID,
            playlist_id=PLAYLIST_ID,
        )
