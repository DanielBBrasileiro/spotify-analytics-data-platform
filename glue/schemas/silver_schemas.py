"""Explicit Spark schemas for curated Silver Parquet datasets."""

from pyspark.sql.types import (
    BooleanType,
    DateType,
    IntegerType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

ARTISTS_SCHEMA = StructType(
    [
        StructField("artist_id", StringType(), False),
        StructField("artist_name", StringType(), False),
        StructField("ingestion_date", DateType(), False),
    ]
)

ALBUMS_SCHEMA = StructType(
    [
        StructField("album_id", StringType(), False),
        StructField("album_name", StringType(), False),
        StructField("album_type", StringType(), True),
        StructField("release_date", StringType(), True),
        StructField("total_tracks", IntegerType(), True),
        StructField("ingestion_date", DateType(), False),
    ]
)

TRACKS_SCHEMA = StructType(
    [
        StructField("track_id", StringType(), False),
        StructField("track_name", StringType(), False),
        StructField("album_id", StringType(), True),
        StructField("duration_ms", IntegerType(), False),
        StructField("is_explicit", BooleanType(), False),
        StructField("is_local", BooleanType(), False),
        StructField("ingestion_date", DateType(), False),
    ]
)

TRACK_ARTISTS_SCHEMA = StructType(
    [
        StructField("track_id", StringType(), False),
        StructField("artist_id", StringType(), False),
        StructField("artist_order", IntegerType(), False),
        StructField("ingestion_date", DateType(), False),
    ]
)

PLAYLIST_SNAPSHOTS_SCHEMA = StructType(
    [
        StructField("playlist_id", StringType(), False),
        StructField("spotify_snapshot_id", StringType(), False),
        StructField("playlist_name", StringType(), False),
        StructField("track_id", StringType(), False),
        StructField("track_position", IntegerType(), False),
        StructField("added_at", TimestampType(), True),
        StructField("snapshot_date", DateType(), False),
        StructField("snapshot_timestamp", TimestampType(), False),
        StructField("pipeline_run_id", StringType(), False),
        StructField("ingestion_date", DateType(), False),
    ]
)

SILVER_SCHEMAS = {
    "artists": ARTISTS_SCHEMA,
    "albums": ALBUMS_SCHEMA,
    "tracks": TRACKS_SCHEMA,
    "track_artists": TRACK_ARTISTS_SCHEMA,
    "playlist_snapshots": PLAYLIST_SNAPSHOTS_SCHEMA,
}
