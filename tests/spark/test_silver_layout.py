"""Silver dataset partition-key contracts."""

from datetime import date
from uuid import UUID

import pytest

from glue.storage.layout import (
    SILVER_DATASETS,
    build_local_silver_partition,
    build_s3_silver_partition_uri,
    build_silver_partition_key,
)

RUN_ID = UUID("123e4567-e89b-42d3-a456-426614174000")
PLAYLIST_ID = "6666666666666666666666"


@pytest.mark.parametrize("dataset", SILVER_DATASETS)
def test_silver_partition_key_uses_canonical_hive_layout(dataset):
    assert build_silver_partition_key(
        dataset,
        date(2026, 9, 12),
        pipeline_run_id=RUN_ID,
        playlist_id=PLAYLIST_ID,
    ) == (f"silver/{dataset}/ingestion_date=2026-09-12/run_id={RUN_ID}/playlist_id={PLAYLIST_ID}/")


def test_local_and_s3_paths_share_the_same_relative_contract(tmp_path):
    local = build_local_silver_partition(
        tmp_path,
        "tracks",
        "2026-09-12",
        pipeline_run_id=RUN_ID,
        playlist_id=PLAYLIST_ID,
    )
    expected = (
        tmp_path
        / f"silver/tracks/ingestion_date=2026-09-12/run_id={RUN_ID}/playlist_id={PLAYLIST_ID}"
    )
    assert local == expected
    assert build_s3_silver_partition_uri(
        "synthetic-bucket",
        "tracks",
        "2026-09-12",
        pipeline_run_id=RUN_ID,
        playlist_id=PLAYLIST_ID,
    ) == (
        "s3://synthetic-bucket/silver/tracks/ingestion_date=2026-09-12/"
        f"run_id={RUN_ID}/playlist_id={PLAYLIST_ID}/"
    )


@pytest.mark.parametrize("value", ["2026-09", "09-12-2026", "", "2026-02-30"])
def test_partition_date_must_be_valid_iso_date(value):
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        build_silver_partition_key("tracks", value, pipeline_run_id=RUN_ID, playlist_id=PLAYLIST_ID)


def test_unknown_dataset_and_nonbare_bucket_are_rejected():
    with pytest.raises(ValueError, match="Unsupported Silver dataset"):
        build_silver_partition_key(
            "unknown", "2026-09-12", pipeline_run_id=RUN_ID, playlist_id=PLAYLIST_ID
        )
    with pytest.raises(ValueError, match="bare S3 bucket"):
        build_s3_silver_partition_uri(
            "s3://bad",
            "tracks",
            "2026-09-12",
            pipeline_run_id=RUN_ID,
            playlist_id=PLAYLIST_ID,
        )


@pytest.mark.parametrize(
    ("run_id", "playlist_id", "message"),
    [
        ("not-a-uuid", PLAYLIST_ID, "UUID v4"),
        (RUN_ID, "", "path-safe"),
        (RUN_ID, "bad/id", "path-safe"),
    ],
)
def test_run_and_playlist_partition_tokens_are_validated(run_id, playlist_id, message):
    with pytest.raises(ValueError, match=message):
        build_silver_partition_key(
            "tracks",
            "2026-09-12",
            pipeline_run_id=run_id,
            playlist_id=playlist_id,
        )
