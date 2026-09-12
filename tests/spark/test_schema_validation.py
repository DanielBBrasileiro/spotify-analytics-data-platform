"""Validation behavior for explicit Spark contracts."""

import pytest
from pyspark.sql.types import StringType, StructField, StructType

from glue.schemas.silver_schemas import ARTISTS_SCHEMA
from glue.schemas.validation import (
    SchemaContractError,
    compare_schema,
    copy_with_declared_nullability,
    require_no_corrupt_records,
    require_non_null_values,
    require_schema,
    required_field_names,
)


def test_compare_schema_reports_missing_type_and_nullability_without_values():
    actual = StructType(
        [
            StructField("artist_id", StringType(), True),
            StructField("artist_name", StringType(), False),
        ]
    )
    expected = StructType(
        [
            StructField("artist_id", StringType(), False),
            StructField("artist_name", StringType(), False),
            StructField("ingestion_date", StringType(), False),
        ]
    )
    assert [(item.field, item.problem) for item in compare_schema(actual, expected)] == [
        ("artist_id", "nullability"),
        ("ingestion_date", "missing"),
    ]


def test_require_schema_raises_sanitized_structural_error(spark):
    frame = spark.createDataFrame([("secret-artist-id", "name")], ["artist_id", "artist_name"])
    with pytest.raises(SchemaContractError) as error:
        require_schema(frame, ARTISTS_SCHEMA, dataset="artists")
    assert "secret-artist-id" not in str(error.value)
    assert "ingestion_date:missing" in str(error.value)


def test_required_field_names_follow_declared_contract():
    assert required_field_names(ARTISTS_SCHEMA) == ("artist_id", "artist_name", "ingestion_date")


def test_require_non_null_values_rejects_required_null_without_leaking_row(spark):
    schema = copy_with_declared_nullability(ARTISTS_SCHEMA, nullable=True)
    frame = spark.createDataFrame([(None, "sensitive name", None)], schema)
    with pytest.raises(SchemaContractError) as error:
        require_non_null_values(frame, ARTISTS_SCHEMA, dataset="artists")
    assert "sensitive name" not in str(error.value)
    assert "nulls in required fields" in str(error.value)


def test_require_non_null_values_rejects_missing_columns(spark):
    frame = spark.createDataFrame([("a",)], ["artist_id"])
    with pytest.raises(SchemaContractError, match="artist_name, ingestion_date"):
        require_non_null_values(frame, ARTISTS_SCHEMA, dataset="artists")


def test_require_no_corrupt_records_accepts_clean_and_rejects_corrupt(spark):
    clean = spark.createDataFrame([(None,)], ["_corrupt_record"])
    require_no_corrupt_records(clean)

    corrupt = spark.createDataFrame([("raw-sensitive-json",)], ["_corrupt_record"])
    with pytest.raises(SchemaContractError) as error:
        require_no_corrupt_records(corrupt)
    assert "raw-sensitive-json" not in str(error.value)


def test_require_no_corrupt_records_requires_declared_column(spark):
    frame = spark.createDataFrame([(1,)], ["value"])
    with pytest.raises(SchemaContractError, match="column is missing"):
        require_no_corrupt_records(frame)
