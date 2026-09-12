"""Partition-scoped Snappy Parquet writer for curated Silver datasets."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from glue.schemas.silver_schemas import SILVER_SCHEMAS
from glue.schemas.validation import SchemaContractError, require_non_null_values

from .layout import normalize_ingestion_date, resolve_silver_partition

PARQUET_TIMESTAMP_CONFIG = "spark.sql.parquet.outputTimestampType"
PARQUET_TIMESTAMP_TYPE = "TIMESTAMP_MICROS"


def _require_declared_types(frame: DataFrame, dataset: str) -> None:
    expected = {field.name: field.dataType for field in SILVER_SCHEMAS[dataset].fields}
    actual = {field.name: field.dataType for field in frame.schema.fields}
    missing = [name for name in expected if name not in actual]
    wrong = [
        name for name, data_type in expected.items() if name in actual and actual[name] != data_type
    ]
    if missing or wrong:
        parts = []
        if missing:
            parts.append("missing=" + ",".join(missing))
        if wrong:
            parts.append("types=" + ",".join(wrong))
        raise SchemaContractError(f"{dataset} writer schema contract failed ({'; '.join(parts)}).")


def write_silver_dataset(
    frame: DataFrame,
    *,
    root: str | Path,
    dataset: str,
    ingestion_date: date | str,
    output_partitions: int = 1,
) -> str:
    """Overwrite one canonical daily Silver partition with Snappy Parquet files."""
    if dataset not in SILVER_SCHEMAS:
        raise ValueError(f"Unsupported Silver dataset: {dataset}.")
    if type(output_partitions) is not int or output_partitions <= 0:
        raise ValueError("output_partitions must be a positive integer.")

    day = normalize_ingestion_date(ingestion_date)
    _require_declared_types(frame, dataset)
    require_non_null_values(frame, SILVER_SCHEMAS[dataset], dataset=dataset)
    wrong_partition = frame.filter(
        F.col("ingestion_date").isNull() | (F.col("ingestion_date") != F.lit(day).cast("date"))
    )
    if wrong_partition.limit(1).count():
        raise SchemaContractError(f"{dataset} contains rows outside ingestion_date={day}.")

    destination = resolve_silver_partition(root, dataset, day)
    spark = frame.sparkSession
    previous_timestamp_type = spark.conf.get(PARQUET_TIMESTAMP_CONFIG, "INT96")
    spark.conf.set(PARQUET_TIMESTAMP_CONFIG, PARQUET_TIMESTAMP_TYPE)
    try:
        (
            frame.coalesce(output_partitions)
            .write.mode("overwrite")
            .option("compression", "snappy")
            .parquet(destination)
        )
    finally:
        spark.conf.set(PARQUET_TIMESTAMP_CONFIG, previous_timestamp_type)
    return destination
