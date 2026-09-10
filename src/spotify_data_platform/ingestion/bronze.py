"""Shared validation and serialization for immutable Bronze playlist snapshots."""

import json
from collections.abc import Mapping
from typing import Any

from .models import PipelineRunMetadata, RunStatus


class BronzeSnapshotValidationError(ValueError):
    """A playlist snapshot does not satisfy the Bronze landing contract."""


def validate_bronze_snapshot(snapshot: Mapping[str, Any], metadata: PipelineRunMetadata) -> None:
    """Validate that source payload and execution metadata describe one complete run."""
    if metadata.status is not RunStatus.SUCCESS:
        raise BronzeSnapshotValidationError(
            "Only complete SUCCESS snapshots may be persisted to Bronze."
        )
    if snapshot.get("playlist_id") != metadata.playlist_id:
        raise BronzeSnapshotValidationError("Snapshot playlist_id does not match run metadata.")
    if snapshot.get("spotify_snapshot_id") != metadata.spotify_snapshot_id:
        raise BronzeSnapshotValidationError(
            "Snapshot spotify_snapshot_id does not match run metadata."
        )
    items = snapshot.get("items")
    if not isinstance(items, list):
        raise BronzeSnapshotValidationError("Snapshot items must be an array.")
    if len(items) != metadata.records_extracted:
        raise BronzeSnapshotValidationError(
            "Snapshot item count does not match records_extracted metadata."
        )
    if not isinstance(snapshot.get("playlist"), dict) or not isinstance(
        snapshot.get("pages"), list
    ):
        raise BronzeSnapshotValidationError("Snapshot does not match the extraction envelope.")


def serialize_bronze_snapshot(snapshot: Mapping[str, Any], metadata: PipelineRunMetadata) -> bytes:
    """Validate and serialize a source-preserving UTF-8 Bronze JSON document."""
    validate_bronze_snapshot(snapshot, metadata)
    try:
        return (json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise BronzeSnapshotValidationError("Snapshot is not JSON serializable.") from exc
