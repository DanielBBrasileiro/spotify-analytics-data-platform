"""Normalize reusable Spotify entities from source-preserving Bronze snapshots."""

from __future__ import annotations

from datetime import date

from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from .common import ingestion_date_column, valid_track_items


def extract_artists(frame: DataFrame, *, ingestion_date: date | str) -> DataFrame:
    """Extract distinct credited artists with provider IDs from valid track items."""
    artists = (
        valid_track_items(frame)
        .select(F.explode_outer("entry.item.artists").alias("artist"))
        .filter(
            F.col("artist").isNotNull()
            & F.col("artist.id").isNotNull()
            & (F.trim(F.col("artist.id")) != F.lit(""))
            & F.col("artist.name").isNotNull()
            & (F.trim(F.col("artist.name")) != F.lit(""))
        )
        .select(
            F.col("artist.id").alias("artist_id"),
            F.col("artist.name").alias("artist_name"),
            ingestion_date_column(ingestion_date).alias("ingestion_date"),
        )
    )
    return artists.dropDuplicates(["artist_id"])
