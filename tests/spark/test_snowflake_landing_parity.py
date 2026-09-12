"""Cross-tier contract: M4 Landing DDL must stay aligned with real M3 schemas."""

import re
from pathlib import Path

from pyspark.sql.types import BooleanType, DateType, IntegerType, StringType, TimestampType

from glue.schemas.silver_schemas import SILVER_SCHEMAS

ROOT = Path(__file__).parents[2]
LANDING_DDL = ROOT / "snowflake" / "ddl" / "06_landing_tables.sql"


def _landing_columns(table: str) -> dict[str, tuple[str, bool]]:
    sql = LANDING_DDL.read_text(encoding="utf-8")
    match = re.search(
        rf"CREATE TABLE IF NOT EXISTS SPOTIFY_ANALYTICS\.LANDING\.{table}\s*\((.*?)\);",
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    )
    assert match, f"missing Landing table {table}"
    columns: dict[str, tuple[str, bool]] = {}
    for raw in match.group(1).splitlines():
        line = raw.strip().rstrip(",")
        if not line:
            continue
        parts = line.split()
        columns[parts[0].lower()] = (parts[1].upper(), "NOT NULL" not in line.upper())
    return columns


def _expected_snowflake_type(data_type) -> str:
    if isinstance(data_type, StringType):
        return "VARCHAR"
    if isinstance(data_type, IntegerType):
        return "INTEGER"
    if isinstance(data_type, BooleanType):
        return "BOOLEAN"
    if isinstance(data_type, DateType):
        return "DATE"
    if isinstance(data_type, TimestampType):
        return "TIMESTAMP_NTZ"
    raise AssertionError(f"unmapped Spark type: {data_type.simpleString()}")


def test_landing_types_and_nullability_follow_actual_silver_schemas():
    for dataset, schema in SILVER_SCHEMAS.items():
        table = f"LANDING_{dataset.upper()}"
        landing = _landing_columns(table)
        silver_names = [field.name for field in schema.fields]
        assert list(landing)[: len(silver_names)] == silver_names
        for field in schema.fields:
            actual_type, actual_nullable = landing[field.name]
            expected_type = _expected_snowflake_type(field.dataType)
            assert actual_type == expected_type or actual_type.startswith(f"{expected_type}(")
            assert actual_nullable is field.nullable
