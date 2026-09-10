"""Validated execution-lineage metadata for Spotify ingestion runs."""

from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

PlaylistId = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9]{22}$")]
NonBlankString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class RunStatus(StrEnum):
    """Lifecycle states shared with the platform observability contract."""

    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"


class PipelineRunMetadata(BaseModel):
    """Core lineage for one playlist observation within a physical pipeline run.

    ``snapshot_date`` is the canonical business observation date. It is deliberately
    independent from ``snapshot_timestamp``, which records the actual UTC capture
    instant and can differ during retries or historical backfills.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    pipeline_run_id: UUID
    spotify_snapshot_id: NonBlankString
    playlist_id: PlaylistId
    snapshot_date: date
    snapshot_timestamp: datetime
    records_extracted: Annotated[int, Field(ge=0, strict=True)]
    status: RunStatus

    @field_validator("pipeline_run_id")
    @classmethod
    def require_uuid_v4(cls, value: UUID) -> UUID:
        """Reject namespace/time UUIDs so run IDs remain non-deterministic UUID v4."""
        if value.version != 4:
            raise ValueError("pipeline_run_id must be a UUID v4.")
        return value

    @field_validator("snapshot_timestamp")
    @classmethod
    def normalize_utc_timestamp(cls, value: datetime) -> datetime:
        """Require an offset-aware capture instant and canonicalize it to UTC."""
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("snapshot_timestamp must be timezone-aware.")
        return value.astimezone(UTC)

    @classmethod
    def from_json(cls, payload: str | bytes | bytearray) -> Self:
        """Validate a JSON representation using Pydantic's JSON-aware parser."""
        return cls.model_validate_json(payload)
