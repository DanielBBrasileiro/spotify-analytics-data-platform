"""Filesystem adapter mirroring the future immutable S3 Bronze object layout."""

import os
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from spotify_data_platform.storage import build_bronze_playlist_key

from .bronze import BronzeSnapshotValidationError, serialize_bronze_snapshot
from .models import PipelineRunMetadata


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
        key = build_bronze_playlist_key(
            ingestion_date=metadata.snapshot_timestamp.date(),
            pipeline_run_id=metadata.pipeline_run_id,
            playlist_id=metadata.playlist_id,
        )
        return self._root / Path(key)

    def write(self, snapshot: Mapping[str, Any], metadata: PipelineRunMetadata) -> Path:
        """Validate lineage and atomically publish a source-preserving JSON snapshot."""
        try:
            serialized = serialize_bronze_snapshot(snapshot, metadata).decode("utf-8")
        except BronzeSnapshotValidationError as exc:
            raise LocalBronzePersistenceError(str(exc)) from exc

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
