"""Canonical local/S3-compatible Silver dataset partition layout."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from uuid import UUID

SILVER_DATASETS = (
    "artists",
    "albums",
    "tracks",
    "track_artists",
    "playlist_snapshots",
    "playlist_observations",
)


def normalize_ingestion_date(value: date | str) -> str:
    """Return a validated ISO calendar date for a Hive partition key."""
    if isinstance(value, date):
        return value.isoformat()
    try:
        return date.fromisoformat(value).isoformat()
    except (TypeError, ValueError) as exc:
        raise ValueError("ingestion_date must be an ISO YYYY-MM-DD date.") from exc


def _normalize_run_id(value: UUID | str) -> str:
    try:
        run_id = value if isinstance(value, UUID) else UUID(str(value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("pipeline_run_id must be a UUID v4.") from exc
    if run_id.version != 4:
        raise ValueError("pipeline_run_id must be a UUID v4.")
    return str(run_id)


def _normalize_playlist_id(value: str) -> str:
    playlist_id = value.strip() if isinstance(value, str) else ""
    if not playlist_id or "/" in playlist_id or "=" in playlist_id:
        raise ValueError("playlist_id must be a nonblank path-safe identifier.")
    return playlist_id


def build_silver_partition_key(
    dataset: str,
    ingestion_date: date | str,
    *,
    pipeline_run_id: UUID | str,
    playlist_id: str,
) -> str:
    """Build one collision-free Silver publication prefix for a physical playlist run."""
    if dataset not in SILVER_DATASETS:
        raise ValueError(f"Unsupported Silver dataset: {dataset}.")
    day = normalize_ingestion_date(ingestion_date)
    run_id = _normalize_run_id(pipeline_run_id)
    source_id = _normalize_playlist_id(playlist_id)
    return f"silver/{dataset}/ingestion_date={day}/run_id={run_id}/playlist_id={source_id}/"


def build_local_silver_partition(
    root: str | Path,
    dataset: str,
    ingestion_date: date | str,
    *,
    pipeline_run_id: UUID | str,
    playlist_id: str,
) -> Path:
    """Resolve a local filesystem partition path from the canonical key contract."""
    return Path(root) / build_silver_partition_key(
        dataset,
        ingestion_date,
        pipeline_run_id=pipeline_run_id,
        playlist_id=playlist_id,
    )


def build_s3_silver_partition_uri(
    bucket: str,
    dataset: str,
    ingestion_date: date | str,
    *,
    pipeline_run_id: UUID | str,
    playlist_id: str,
) -> str:
    """Render the future S3 target URI without making any AWS API call."""
    normalized_bucket = bucket.strip()
    if not normalized_bucket or "/" in normalized_bucket or normalized_bucket.startswith("s3:"):
        raise ValueError("bucket must be a bare S3 bucket name.")
    return f"s3://{normalized_bucket}/" + build_silver_partition_key(
        dataset,
        ingestion_date,
        pipeline_run_id=pipeline_run_id,
        playlist_id=playlist_id,
    )


def resolve_silver_partition(
    root: str | Path,
    dataset: str,
    ingestion_date: date | str,
    *,
    pipeline_run_id: UUID | str,
    playlist_id: str,
) -> str:
    """Resolve a local path or an S3 URI without performing any storage operation."""
    raw_root = str(root)
    if raw_root.startswith("s3://"):
        return (
            raw_root.rstrip("/")
            + "/"
            + build_silver_partition_key(
                dataset,
                ingestion_date,
                pipeline_run_id=pipeline_run_id,
                playlist_id=playlist_id,
            )
        )
    if "://" in raw_root:
        raise ValueError("Only local filesystem roots and s3:// roots are supported.")
    return str(
        build_local_silver_partition(
            root,
            dataset,
            ingestion_date,
            pipeline_run_id=pipeline_run_id,
            playlist_id=playlist_id,
        )
    )
