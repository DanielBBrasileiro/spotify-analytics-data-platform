"""Explicit Spark schema for source-preserving Bronze playlist snapshots.

The Bronze object is the immutable extraction envelope written by M2. Spark reads only
fields needed by M3; unknown future source fields remain in Bronze and are intentionally
ignored by the curated Silver contract.
"""

from pyspark.sql.types import (
    ArrayType,
    BooleanType,
    IntegerType,
    StringType,
    StructField,
    StructType,
)

ARTIST_SCHEMA = StructType(
    [
        StructField("id", StringType(), True),
        StructField("name", StringType(), True),
        StructField("type", StringType(), True),
    ]
)

ALBUM_SCHEMA = StructType(
    [
        StructField("id", StringType(), True),
        StructField("name", StringType(), True),
        StructField("album_type", StringType(), True),
        StructField("release_date", StringType(), True),
        StructField("total_tracks", IntegerType(), True),
        StructField("artists", ArrayType(ARTIST_SCHEMA, containsNull=True), True),
    ]
)

ITEM_OBJECT_SCHEMA = StructType(
    [
        StructField("id", StringType(), True),
        StructField("name", StringType(), True),
        StructField("type", StringType(), True),
        StructField("duration_ms", IntegerType(), True),
        StructField("explicit", BooleanType(), True),
        StructField("is_local", BooleanType(), True),
        StructField("album", ALBUM_SCHEMA, True),
        StructField("artists", ArrayType(ARTIST_SCHEMA, containsNull=True), True),
    ]
)

PLAYLIST_ITEM_SCHEMA = StructType(
    [
        StructField("added_at", StringType(), True),
        StructField("is_local", BooleanType(), True),
        StructField("item", ITEM_OBJECT_SCHEMA, True),
    ]
)

OWNER_SCHEMA = StructType(
    [
        StructField("id", StringType(), True),
        StructField("display_name", StringType(), True),
    ]
)

PLAYLIST_SCHEMA = StructType(
    [
        StructField("id", StringType(), True),
        StructField("name", StringType(), True),
        StructField("snapshot_id", StringType(), True),
        StructField("collaborative", BooleanType(), True),
        StructField("owner", OWNER_SCHEMA, True),
    ]
)

PAGE_SCHEMA = StructType(
    [
        StructField("offset", IntegerType(), True),
        StructField("limit", IntegerType(), True),
        StructField("total", IntegerType(), True),
        StructField("next", StringType(), True),
        StructField("items", ArrayType(PLAYLIST_ITEM_SCHEMA, containsNull=True), True),
    ]
)

BRONZE_PLAYLIST_SNAPSHOT_SCHEMA = StructType(
    [
        StructField("playlist_id", StringType(), True),
        StructField("spotify_snapshot_id", StringType(), True),
        StructField("playlist", PLAYLIST_SCHEMA, True),
        StructField("pages", ArrayType(PAGE_SCHEMA, containsNull=True), True),
        StructField("items", ArrayType(PLAYLIST_ITEM_SCHEMA, containsNull=True), True),
        StructField("_corrupt_record", StringType(), True),
    ]
)
