"""Canonical local/S3-compatible Silver dataset partition layout."""

from __future__ import annotations

from datetime import date
from pathlib import Path

SILVER_DATASETS = (
    "artists",
    "albums",
    "tracks",
    "track_artists",
    "playlist_snapshots",
)


def normalize_ingestion_date(value: date | str) -> str:
    """Return a validated ISO calendar date for a Hive partition key."""
    if isinstance(value, date):
        return value.isoformat()
    try:
        return date.fromisoformat(value).isoformat()
    except (TypeError, ValueError) as exc:
        raise ValueError("ingestion_date must be an ISO YYYY-MM-DD date.") from exc


def build_silver_partition_key(dataset: str, ingestion_date: date | str) -> str:
    """Build the canonical relative Silver partition prefix."""
    if dataset not in SILVER_DATASETS:
        raise ValueError(f"Unsupported Silver dataset: {dataset}.")
    day = normalize_ingestion_date(ingestion_date)
    return f"silver/{dataset}/ingestion_date={day}/"


def build_local_silver_partition(
    root: str | Path,
    dataset: str,
    ingestion_date: date | str,
) -> Path:
    """Resolve a local filesystem partition path from the canonical key contract."""
    return Path(root) / build_silver_partition_key(dataset, ingestion_date)


def build_s3_silver_partition_uri(
    bucket: str,
    dataset: str,
    ingestion_date: date | str,
) -> str:
    """Render the future S3 target URI without making any AWS API call."""
    normalized_bucket = bucket.strip()
    if not normalized_bucket or "/" in normalized_bucket or normalized_bucket.startswith("s3:"):
        raise ValueError("bucket must be a bare S3 bucket name.")
    return f"s3://{normalized_bucket}/{build_silver_partition_key(dataset, ingestion_date)}"


def resolve_silver_partition(
    root: str | Path,
    dataset: str,
    ingestion_date: date | str,
) -> str:
    """Resolve a local path or an S3 URI without performing any storage operation."""
    raw_root = str(root)
    if raw_root.startswith("s3://"):
        return raw_root.rstrip("/") + "/" + build_silver_partition_key(dataset, ingestion_date)
    if "://" in raw_root:
        raise ValueError("Only local filesystem roots and s3:// roots are supported.")
    return str(build_local_silver_partition(root, dataset, ingestion_date))
