"""Shared DataFrame primitives for technical Bronze-to-Silver normalization."""

from __future__ import annotations

from datetime import date

from pyspark.sql import DataFrame
from pyspark.sql import functions as F


def with_playlist_items(frame: DataFrame) -> DataFrame:
    """Explode consolidated top-level Bronze items while preserving source position."""
    return frame.select(
        "playlist_id",
        "spotify_snapshot_id",
        "playlist",
        F.posexplode_outer("items").alias("track_position", "entry"),
    )


def valid_track_items(frame: DataFrame) -> DataFrame:
    """Return direct 2026 track items with stable nonblank Spotify track IDs."""
    exploded = with_playlist_items(frame)
    track_id = F.trim(F.col("entry.item.id"))
    return exploded.filter(
        F.col("entry.item").isNotNull()
        & (F.col("entry.item.type") == F.lit("track"))
        & F.col("entry.item.id").isNotNull()
        & (track_id != F.lit(""))
    )


def ingestion_date_column(value: date | str):
    """Create the canonical DateType ingestion partition value."""
    return F.lit(value.isoformat() if isinstance(value, date) else value).cast("date")
