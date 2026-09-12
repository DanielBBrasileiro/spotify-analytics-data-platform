"""Partition-scoped local Parquet serialization contracts."""

from datetime import date
from pathlib import Path

import pytest
from pyspark.sql import functions as F

from glue.schemas.validation import SchemaContractError
from glue.storage.parquet import write_silver_dataset
from glue.transforms.entities import extract_tracks
from tests.spark.helpers import bronze_frame


def _parquet_files(destination: str):
    return sorted(Path(destination).glob("*.parquet"))


def _first_column_codec(spark, parquet_file: Path):
    jvm = spark._jvm
    footer = jvm.org.apache.parquet.hadoop.ParquetFileReader.readFooter(
        spark._jsc.hadoopConfiguration(),
        jvm.org.apache.hadoop.fs.Path(str(parquet_file)),
    )
    return footer.getBlocks().get(0).getColumns().get(0).getCodec().name()


def test_write_silver_dataset_creates_hive_path_retains_date_and_uses_snappy(spark, tmp_path):
    frame = extract_tracks(bronze_frame(spark), ingestion_date=date(2026, 9, 12))
    destination = write_silver_dataset(
        frame,
        root=tmp_path,
        dataset="tracks",
        ingestion_date="2026-09-12",
    )

    assert Path(destination) == tmp_path / "silver/tracks/ingestion_date=2026-09-12"
    files = _parquet_files(destination)
    assert len(files) == 1
    assert _first_column_codec(spark, files[0]) == "SNAPPY"
    restored = spark.read.parquet(destination)
    assert "ingestion_date" in restored.columns
    assert restored.one().ingestion_date.isoformat() == "2026-09-12"


def test_partition_write_is_overwrite_scoped_to_the_requested_day(spark, tmp_path):
    base = extract_tracks(bronze_frame(spark), ingestion_date="2026-09-12")
    destination = write_silver_dataset(
        base,
        root=tmp_path,
        dataset="tracks",
        ingestion_date="2026-09-12",
    )
    replacement = base.withColumn("track_name", F.lit("Replacement"))
    write_silver_dataset(
        replacement,
        root=tmp_path,
        dataset="tracks",
        ingestion_date="2026-09-12",
    )
    rows = spark.read.parquet(destination).collect()
    assert len(rows) == 1
    assert rows[0].track_name == "Replacement"


def test_writer_rejects_mixed_partition_dates_and_invalid_partition_count(spark, tmp_path):
    frame = extract_tracks(bronze_frame(spark), ingestion_date="2026-09-12")
    wrong = frame.withColumn("ingestion_date", F.lit("2026-09-11").cast("date"))
    with pytest.raises(SchemaContractError, match="outside ingestion_date"):
        write_silver_dataset(
            wrong,
            root=tmp_path,
            dataset="tracks",
            ingestion_date="2026-09-12",
        )
    with pytest.raises(ValueError, match="positive integer"):
        write_silver_dataset(
            frame,
            root=tmp_path,
            dataset="tracks",
            ingestion_date="2026-09-12",
            output_partitions=0,
        )


def test_writer_rejects_schema_drift_before_creating_output(spark, tmp_path):
    frame = extract_tracks(bronze_frame(spark), ingestion_date="2026-09-12").drop("duration_ms")
    with pytest.raises(SchemaContractError, match="writer schema contract"):
        write_silver_dataset(
            frame,
            root=tmp_path,
            dataset="tracks",
            ingestion_date="2026-09-12",
        )
    assert not (tmp_path / "silver").exists()
