"""Canonical Amazon S3 object naming for the Bronze playlist landing zone."""

import ipaddress
import re
from datetime import date, datetime
from uuid import UUID

BRONZE_PLAYLIST_PREFIX = "bronze/spotify/playlist_tracks"

_PLAYLIST_ID_RE = re.compile(r"^[A-Za-z0-9]{22}$")
_BUCKET_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$")
_RESERVED_BUCKET_PREFIXES = ("xn--", "sthree-", "amzn-s3-demo-")
_RESERVED_BUCKET_SUFFIXES = ("-s3alias", "--ol-s3", ".mrap", "--x-s3", "--table-s3")


class S3PathValidationError(ValueError):
    """An S3 bucket name or Bronze key component violates the storage contract."""


def build_bronze_playlist_key(
    *, ingestion_date: date, pipeline_run_id: UUID, playlist_id: str
) -> str:
    """Build the canonical Hive-style Bronze object key for one playlist snapshot.

    Inputs are deliberately constrained rather than accepting an arbitrary prefix.
    That keeps the returned key free of relative path segments and guarantees the
    same partition hierarchy for local persistence, S3, Athena, and Snowflake.
    """
    _validate_ingestion_date(ingestion_date)
    _validate_pipeline_run_id(pipeline_run_id)
    _validate_playlist_id(playlist_id)
    return (
        f"{BRONZE_PLAYLIST_PREFIX}/"
        f"ingestion_date={ingestion_date.isoformat()}/"
        f"run_id={pipeline_run_id}/"
        f"playlist_{playlist_id}.json"
    )


def build_bronze_playlist_uri(
    bucket: str,
    *,
    ingestion_date: date,
    pipeline_run_id: UUID,
    playlist_id: str,
) -> str:
    """Build an ``s3://`` URI for a canonical Bronze playlist object."""
    _validate_general_purpose_bucket_name(bucket)
    key = build_bronze_playlist_key(
        ingestion_date=ingestion_date,
        pipeline_run_id=pipeline_run_id,
        playlist_id=playlist_id,
    )
    return f"s3://{bucket}/{key}"


def _validate_ingestion_date(value: date) -> None:
    if not isinstance(value, date) or isinstance(value, datetime):
        raise S3PathValidationError("ingestion_date must be a datetime.date value.")


def _validate_pipeline_run_id(value: UUID) -> None:
    if not isinstance(value, UUID) or value.version != 4:
        raise S3PathValidationError("pipeline_run_id must be a UUID v4 value.")


def _validate_playlist_id(value: str) -> None:
    if not isinstance(value, str) or _PLAYLIST_ID_RE.fullmatch(value) is None:
        raise S3PathValidationError("playlist_id must be a 22-character base62 identifier.")


def _validate_general_purpose_bucket_name(value: str) -> None:
    """Validate AWS general-purpose bucket syntax without checking availability."""
    if not isinstance(value, str) or _BUCKET_NAME_RE.fullmatch(value) is None:
        raise S3PathValidationError("bucket must use valid S3 general-purpose bucket syntax.")
    if ".." in value:
        raise S3PathValidationError("bucket names cannot contain adjacent periods.")
    if value.startswith(_RESERVED_BUCKET_PREFIXES) or value.endswith(_RESERVED_BUCKET_SUFFIXES):
        raise S3PathValidationError("bucket name uses an AWS-reserved prefix or suffix.")
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return
    raise S3PathValidationError("bucket names cannot be formatted as IP addresses.")
