"""Deterministic technical deduplication for Silver transformation outputs."""

from __future__ import annotations

from collections.abc import Sequence

from pyspark.sql import Column, DataFrame, Window
from pyspark.sql import functions as F


def deterministic_dedupe(
    frame: DataFrame,
    *,
    keys: Sequence[str],
    ordering: Sequence[Column] = (),
) -> DataFrame:
    """Keep one deterministic row per technical key, with a stable final tie-breaker."""
    if not keys:
        raise ValueError("At least one deduplication key is required.")
    missing = [key for key in keys if key not in frame.columns]
    if missing:
        raise ValueError(f"Missing deduplication keys: {', '.join(missing)}.")

    fingerprint_fields = [F.col(name) for name in sorted(frame.columns)]
    ranked = frame.withColumn(
        "_dedupe_fingerprint",
        F.sha2(F.to_json(F.struct(*fingerprint_fields)), 256),
    )
    window = Window.partitionBy(*keys).orderBy(
        *ordering,
        F.col("_dedupe_fingerprint").asc(),
    )
    return (
        ranked.withColumn("_dedupe_rank", F.row_number().over(window))
        .filter(F.col("_dedupe_rank") == 1)
        .drop("_dedupe_rank", "_dedupe_fingerprint")
    )
