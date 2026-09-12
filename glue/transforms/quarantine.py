"""Classify Bronze playlist items that cannot enter provider-backed Silver datasets."""

from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from .common import with_playlist_items


def rejected_playlist_items(frame: DataFrame) -> DataFrame:
    """Return sanitized rejection metadata without persisting raw source payloads."""
    exploded = with_playlist_items(frame)
    item_type = F.col("entry.item.type")
    track_id = F.trim(F.col("entry.item.id"))
    is_local = F.coalesce(F.col("entry.item.is_local"), F.col("entry.is_local"), F.lit(False))
    reason = (
        F.when(F.col("entry").isNull() | F.col("entry.item").isNull(), "UNAVAILABLE_ITEM")
        .when(item_type.isNull(), "UNSUPPORTED_ITEM_TYPE")
        .when(item_type != F.lit("track"), "UNSUPPORTED_ITEM_TYPE")
        .when(
            is_local & (F.col("entry.item.id").isNull() | (track_id == F.lit(""))),
            "LOCAL_TRACK_WITHOUT_ID",
        )
        .when(F.col("entry.item.id").isNull() | (track_id == F.lit("")), "MISSING_TRACK_ID")
    )
    return (
        exploded.withColumn("rejection_reason", reason)
        .filter(F.col("track_position").isNotNull())
        .filter(F.col("rejection_reason").isNotNull())
        .select(
            "playlist_id",
            "spotify_snapshot_id",
            F.col("track_position").cast("int").alias("track_position"),
            F.col("entry.item.type").alias("item_type"),
            is_local.alias("is_local"),
            "rejection_reason",
        )
    )
