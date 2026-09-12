"""Reusable Spark schema and required-value validation contracts."""

from __future__ import annotations

from dataclasses import dataclass

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import StructField, StructType


@dataclass(frozen=True)
class SchemaMismatch:
    """One structural mismatch without leaking row contents."""

    field: str
    problem: str


class SchemaContractError(ValueError):
    """A Spark DataFrame violates an explicit data contract."""


def compare_schema(actual: StructType, expected: StructType) -> tuple[SchemaMismatch, ...]:
    """Return deterministic structural differences for expected fields."""
    actual_by_name = {field.name: field for field in actual.fields}
    mismatches: list[SchemaMismatch] = []
    for expected_field in expected.fields:
        actual_field = actual_by_name.get(expected_field.name)
        if actual_field is None:
            mismatches.append(SchemaMismatch(expected_field.name, "missing"))
            continue
        if actual_field.dataType != expected_field.dataType:
            mismatches.append(SchemaMismatch(expected_field.name, "type"))
        if expected_field.nullable is False and actual_field.nullable is True:
            mismatches.append(SchemaMismatch(expected_field.name, "nullability"))
    return tuple(mismatches)


def require_schema(frame: DataFrame, expected: StructType, *, dataset: str) -> None:
    """Raise a sanitized error if expected fields/types/nullability are violated."""
    mismatches = compare_schema(frame.schema, expected)
    if mismatches:
        summary = ", ".join(f"{item.field}:{item.problem}" for item in mismatches)
        raise SchemaContractError(f"{dataset} schema contract failed ({summary}).")


def require_no_corrupt_records(frame: DataFrame, *, column: str = "_corrupt_record") -> None:
    """Reject permissive JSON parse failures without emitting raw corrupt payloads."""
    if column not in frame.columns:
        raise SchemaContractError("Bronze corrupt-record column is missing.")
    if frame.filter(F.col(column).isNotNull()).limit(1).count():
        raise SchemaContractError("Bronze JSON contains corrupt records.")


def required_field_names(schema: StructType) -> tuple[str, ...]:
    """List top-level non-nullable fields in declaration order."""
    return tuple(field.name for field in schema.fields if not field.nullable)


def require_non_null_values(frame: DataFrame, schema: StructType, *, dataset: str) -> None:
    """Reject rows with nulls in top-level fields declared non-nullable."""
    required = required_field_names(schema)
    missing = [name for name in required if name not in frame.columns]
    if missing:
        raise SchemaContractError(f"{dataset} is missing required columns: {', '.join(missing)}.")
    if not required:
        return
    predicate = F.lit(False)
    for name in required:
        predicate = predicate | F.col(name).isNull()
    if frame.filter(predicate).limit(1).count():
        raise SchemaContractError(f"{dataset} contains nulls in required fields.")


def copy_with_declared_nullability(schema: StructType, *, nullable: bool) -> StructType:
    """Test/helper utility for rebuilding top-level nullability deterministically."""
    return StructType(
        [
            StructField(field.name, field.dataType, nullable, field.metadata)
            for field in schema.fields
        ]
    )
