"""Silver dataset partition-key contracts."""

from datetime import date

import pytest

from glue.storage.layout import (
    SILVER_DATASETS,
    build_local_silver_partition,
    build_s3_silver_partition_uri,
    build_silver_partition_key,
)


@pytest.mark.parametrize("dataset", SILVER_DATASETS)
def test_silver_partition_key_uses_canonical_hive_layout(dataset):
    assert build_silver_partition_key(dataset, date(2026, 9, 12)) == (
        f"silver/{dataset}/ingestion_date=2026-09-12/"
    )


def test_local_and_s3_paths_share_the_same_relative_contract(tmp_path):
    local = build_local_silver_partition(tmp_path, "tracks", "2026-09-12")
    assert local == tmp_path / "silver/tracks/ingestion_date=2026-09-12"
    assert build_s3_silver_partition_uri("synthetic-bucket", "tracks", "2026-09-12") == (
        "s3://synthetic-bucket/silver/tracks/ingestion_date=2026-09-12/"
    )


@pytest.mark.parametrize("value", ["2026-09", "09-12-2026", "", "2026-02-30"])
def test_partition_date_must_be_valid_iso_date(value):
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        build_silver_partition_key("tracks", value)


def test_unknown_dataset_and_nonbare_bucket_are_rejected():
    with pytest.raises(ValueError, match="Unsupported Silver dataset"):
        build_silver_partition_key("unknown", "2026-09-12")
    with pytest.raises(ValueError, match="bare S3 bucket"):
        build_s3_silver_partition_uri("s3://bad", "tracks", "2026-09-12")
