"""Normalize reusable Spotify entities from source-preserving Bronze snapshots."""

from __future__ import annotations

from datetime import date

from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from .common import ingestion_date_column, valid_track_items
from .dedup import deterministic_dedupe


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
    return deterministic_dedupe(
        artists,
        keys=("artist_id",),
        ordering=(F.col("artist_name").asc_nulls_last(),),
    )


def extract_albums(frame: DataFrame, *, ingestion_date: date | str) -> DataFrame:
    """Extract distinct provider-backed albums from valid track items."""
    albums = (
        valid_track_items(frame)
        .select(F.col("entry.item.album").alias("album"))
        .filter(
            F.col("album").isNotNull()
            & F.col("album.id").isNotNull()
            & (F.trim(F.col("album.id")) != F.lit(""))
            & F.col("album.name").isNotNull()
            & (F.trim(F.col("album.name")) != F.lit(""))
        )
        .select(
            F.col("album.id").alias("album_id"),
            F.col("album.name").alias("album_name"),
            F.col("album.album_type").alias("album_type"),
            F.col("album.release_date").alias("release_date"),
            F.col("album.total_tracks").alias("total_tracks"),
            ingestion_date_column(ingestion_date).alias("ingestion_date"),
        )
    )
    return deterministic_dedupe(
        albums,
        keys=("album_id",),
        ordering=(
            F.col("album_name").asc_nulls_last(),
            F.col("release_date").asc_nulls_last(),
        ),
    )


def extract_tracks(frame: DataFrame, *, ingestion_date: date | str) -> DataFrame:
    """Extract provider-backed track entities from valid music items."""
    tracks = (
        valid_track_items(frame)
        .filter(
            F.col("entry.item.name").isNotNull()
            & (F.trim(F.col("entry.item.name")) != F.lit(""))
            & F.col("entry.item.duration_ms").isNotNull()
            & F.col("entry.item.explicit").isNotNull()
            & F.col("entry.item.is_local").isNotNull()
        )
        .select(
            F.col("entry.item.id").alias("track_id"),
            F.col("entry.item.name").alias("track_name"),
            F.col("entry.item.album.id").alias("album_id"),
            F.col("entry.item.duration_ms").alias("duration_ms"),
            F.col("entry.item.explicit").alias("is_explicit"),
            F.col("entry.item.is_local").alias("is_local"),
            ingestion_date_column(ingestion_date).alias("ingestion_date"),
        )
    )
    return deterministic_dedupe(
        tracks,
        keys=("track_id",),
        ordering=(F.col("track_name").asc_nulls_last(),),
    )


def extract_track_artists(frame: DataFrame, *, ingestion_date: date | str) -> DataFrame:
    """Explode credited artists while preserving source billing order."""
    bridge = (
        valid_track_items(frame)
        .select(
            F.col("entry.item.id").alias("track_id"),
            F.posexplode_outer("entry.item.artists").alias("artist_order", "artist"),
        )
        .filter(
            F.col("artist").isNotNull()
            & F.col("artist.id").isNotNull()
            & (F.trim(F.col("artist.id")) != F.lit(""))
        )
        .select(
            "track_id",
            F.col("artist.id").alias("artist_id"),
            F.col("artist_order").cast("int").alias("artist_order"),
            ingestion_date_column(ingestion_date).alias("ingestion_date"),
        )
    )
    return deterministic_dedupe(
        bridge,
        keys=("track_id", "artist_id", "artist_order"),
    )
