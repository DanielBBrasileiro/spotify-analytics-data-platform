"""Normalize historical playlist slot observations with explicit run lineage."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from uuid import UUID

from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from .common import ingestion_date_column, valid_track_items
from .dedup import deterministic_dedupe


@dataclass(frozen=True)
class SnapshotLineage:
    """Physical execution metadata intentionally kept outside immutable Bronze source JSON."""

    pipeline_run_id: UUID
    snapshot_date: date
    snapshot_timestamp: datetime
    ingestion_date: date

    def __post_init__(self) -> None:
        if self.pipeline_run_id.version != 4:
            raise ValueError("pipeline_run_id must be UUID v4.")
        if self.snapshot_timestamp.tzinfo is None or self.snapshot_timestamp.utcoffset() is None:
            raise ValueError("snapshot_timestamp must be timezone-aware.")

    @property
    def snapshot_timestamp_utc(self) -> datetime:
        """Canonical UTC instant used by Spark TimestampType output."""
        return self.snapshot_timestamp.astimezone(UTC)


def extract_playlist_snapshots(frame: DataFrame, *, lineage: SnapshotLineage) -> DataFrame:
    """Build one valid provider-backed track slot observation per source array position."""
    rows = valid_track_items(frame).filter(
        F.col("playlist_id").isNotNull()
        & (F.trim(F.col("playlist_id")) != F.lit(""))
        & F.col("spotify_snapshot_id").isNotNull()
        & (F.trim(F.col("spotify_snapshot_id")) != F.lit(""))
        & F.col("playlist.name").isNotNull()
        & (F.trim(F.col("playlist.name")) != F.lit(""))
    )
    normalized = rows.select(
        "playlist_id",
        "spotify_snapshot_id",
        F.col("playlist.name").alias("playlist_name"),
        F.col("entry.item.id").alias("track_id"),
        F.col("track_position").cast("int").alias("track_position"),
        F.to_timestamp(F.col("entry.added_at")).alias("added_at"),
        F.lit(lineage.snapshot_date.isoformat()).cast("date").alias("snapshot_date"),
        F.to_timestamp(F.lit(lineage.snapshot_timestamp_utc.isoformat())).alias(
            "snapshot_timestamp"
        ),
        F.lit(str(lineage.pipeline_run_id)).alias("pipeline_run_id"),
        ingestion_date_column(lineage.ingestion_date).alias("ingestion_date"),
    )
    return deduplicate_playlist_snapshots(normalized)


def deduplicate_playlist_snapshots(frame: DataFrame) -> DataFrame:
    """Resolve retry/backfill duplicates at the canonical daily playlist-slot grain."""
    return deterministic_dedupe(
        frame,
        keys=("playlist_id", "snapshot_date", "track_position"),
        ordering=(
            F.col("snapshot_timestamp").desc_nulls_last(),
            F.col("pipeline_run_id").desc_nulls_last(),
        ),
    )
