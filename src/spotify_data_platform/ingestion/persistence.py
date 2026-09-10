"""Filesystem adapter mirroring the future immutable S3 Bronze object layout."""

import json
import os
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .models import PipelineRunMetadata, RunStatus


class LocalBronzePersistenceError(Exception):
    """A validated snapshot could not be safely persisted to local Bronze storage."""


class LocalBronzeWriter:
    """Persist successful snapshots without overwriting an existing physical run.

    The local layout intentionally mirrors the future S3 key hierarchy while keeping
    all cloud APIs out of M1. Telemetry stays separate from the source snapshot JSON.
    """

    def __init__(self, root: str | Path = "data") -> None:
        self._root = Path(root)

    def destination_for(self, metadata: PipelineRunMetadata) -> Path:
        """Return the Bronze path derived from physical capture lineage."""
        ingestion_date = metadata.snapshot_timestamp.date().isoformat()
        return (
            self._root
            / "bronze"
            / "spotify"
            / "playlist_tracks"
            / f"ingestion_date={ingestion_date}"
            / f"run_id={metadata.pipeline_run_id}"
            / f"playlist_{metadata.playlist_id}.json"
        )

    def write(self, snapshot: Mapping[str, Any], metadata: PipelineRunMetadata) -> Path:
        """Validate lineage and atomically publish a source-preserving JSON snapshot."""
        self._validate_snapshot(snapshot, metadata)
        try:
            serialized = json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n"
        except (TypeError, ValueError) as exc:
            raise LocalBronzePersistenceError("Snapshot is not JSON serializable.") from exc

        destination = self.destination_for(metadata)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=destination.parent,
                prefix=f".{destination.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary = Path(handle.name)
                handle.write(serialized)
                handle.flush()
                os.fsync(handle.fileno())

            try:
                os.link(temporary, destination)
            except FileExistsError as exc:
                raise LocalBronzePersistenceError(
                    "Bronze snapshot already exists; immutable outputs are never overwritten."
                ) from exc
            except OSError as exc:
                raise LocalBronzePersistenceError("Could not publish Bronze snapshot.") from exc
            return destination
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    @staticmethod
    def _validate_snapshot(snapshot: Mapping[str, Any], metadata: PipelineRunMetadata) -> None:
        if metadata.status is not RunStatus.SUCCESS:
            raise LocalBronzePersistenceError(
                "Only complete SUCCESS snapshots may be persisted to Bronze."
            )
        if snapshot.get("playlist_id") != metadata.playlist_id:
            raise LocalBronzePersistenceError("Snapshot playlist_id does not match run metadata.")
        if snapshot.get("spotify_snapshot_id") != metadata.spotify_snapshot_id:
            raise LocalBronzePersistenceError(
                "Snapshot spotify_snapshot_id does not match run metadata."
            )
        items = snapshot.get("items")
        if not isinstance(items, list):
            raise LocalBronzePersistenceError("Snapshot items must be an array.")
        if len(items) != metadata.records_extracted:
            raise LocalBronzePersistenceError(
                "Snapshot item count does not match records_extracted metadata."
            )
        if not isinstance(snapshot.get("playlist"), dict) or not isinstance(
            snapshot.get("pages"), list
        ):
            raise LocalBronzePersistenceError("Snapshot does not match the extraction envelope.")
