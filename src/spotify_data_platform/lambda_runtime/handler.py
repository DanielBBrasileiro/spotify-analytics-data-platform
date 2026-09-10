"""Validated AWS Lambda handler for Spotify playlist extraction into S3 Bronze."""

import importlib
import os
import time
from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime
from typing import Annotated, Any, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from spotify_data_platform.auth import InvalidGrantException
from spotify_data_platform.extraction import PageFetchTelemetry, PlaylistItemsExtractor
from spotify_data_platform.ingestion import PipelineRunMetadata, RunStatus

from .credentials import get_default_auth_client, invalidate_runtime_caches
from .s3_writer import S3BronzeWriter, S3Client
from .telemetry import LambdaEvent, LambdaTelemetryLogger, configure_lambda_logger

PlaylistId = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9]{22}$")]


class LambdaConfigurationError(RuntimeError):
    """The Lambda runtime is missing required non-secret configuration."""


class Extractor(Protocol):
    """Minimal playlist extraction boundary used by the Lambda service."""

    def extract(self, playlist_id: str) -> Mapping[str, Any]:
        """Return one complete, version-checked playlist observation."""
        ...


class LambdaExtractionRequest(BaseModel):
    """Validated event contract supplied by the future Airflow Lambda invocation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    playlist_ids: Annotated[list[PlaylistId], Field(min_length=1, max_length=100)]
    pipeline_run_id: UUID
    snapshot_date: date

    @field_validator("pipeline_run_id")
    @classmethod
    def require_uuid_v4(cls, value: UUID) -> UUID:
        if value.version != 4:
            raise ValueError("pipeline_run_id must be a UUID v4.")
        return value

    @field_validator("playlist_ids")
    @classmethod
    def require_unique_playlists(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("playlist_ids must not contain duplicates.")
        return value


class LambdaExtractorService:
    """Coordinate extraction, lineage metadata, and immutable S3 publication."""

    def __init__(
        self,
        extractor: Extractor,
        writer: S3BronzeWriter,
        *,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        monotonic: Callable[[], float] = time.monotonic,
        telemetry: LambdaTelemetryLogger | None = None,
    ) -> None:
        self._extractor = extractor
        self._writer = writer
        self._now = now
        self._monotonic = monotonic
        self._telemetry = telemetry

    def run(self, request: LambdaExtractionRequest) -> dict[str, Any]:
        """Process all requested playlists under one physical pipeline execution ID."""
        started_at = self._monotonic()
        objects: list[dict[str, Any]] = []
        total_records = 0

        for playlist_id in request.playlist_ids:
            playlist_started_at = self._monotonic() if self._telemetry is not None else None
            snapshot_id: str | None = None
            self._emit(
                LambdaEvent.EXTRACTION_START,
                request,
                playlist_id,
                snapshot_id,
                duration_ms=0.0,
                status="RUNNING",
            )
            try:
                snapshot = self._extractor.extract(playlist_id)
                snapshot_id = snapshot["spotify_snapshot_id"]
                captured_at = self._now()
                metadata = PipelineRunMetadata(
                    pipeline_run_id=request.pipeline_run_id,
                    spotify_snapshot_id=snapshot_id,
                    playlist_id=playlist_id,
                    snapshot_date=request.snapshot_date,
                    snapshot_timestamp=captured_at,
                    records_extracted=len(snapshot["items"]),
                    status=RunStatus.SUCCESS,
                )
                uri = self._writer.write(snapshot, metadata)
                if playlist_started_at is not None:
                    self._emit(
                        LambdaEvent.S3_WRITE_SUCCESS,
                        request,
                        playlist_id,
                        snapshot_id,
                        duration_ms=self._elapsed_ms(playlist_started_at),
                        status="RUNNING",
                        records_extracted=metadata.records_extracted,
                        s3_uri=uri,
                    )
                total_records += metadata.records_extracted
                objects.append(
                    {
                        "playlist_id": playlist_id,
                        "spotify_snapshot_id": metadata.spotify_snapshot_id,
                        "records_extracted": metadata.records_extracted,
                        "snapshot_timestamp": metadata.snapshot_timestamp.isoformat().replace(
                            "+00:00", "Z"
                        ),
                        "s3_uri": uri,
                    }
                )
                if playlist_started_at is not None:
                    self._emit(
                        LambdaEvent.EXTRACTION_COMPLETE,
                        request,
                        playlist_id,
                        snapshot_id,
                        duration_ms=self._elapsed_ms(playlist_started_at),
                        status="SUCCESS",
                        records_extracted=metadata.records_extracted,
                        snapshot_timestamp=metadata.snapshot_timestamp.isoformat().replace(
                            "+00:00", "Z"
                        ),
                    )
            except Exception as exc:
                if playlist_started_at is not None:
                    self._emit(
                        LambdaEvent.EXTRACTION_FAILED,
                        request,
                        playlist_id,
                        snapshot_id,
                        duration_ms=self._elapsed_ms(playlist_started_at),
                        status="FAILED",
                        error_type=type(exc).__name__,
                    )
                raise

        elapsed_ms = max(0.0, (self._monotonic() - started_at) * 1000.0)
        return {
            "statusCode": 200,
            "pipeline_run_id": str(request.pipeline_run_id),
            "snapshot_date": request.snapshot_date.isoformat(),
            "playlist_count": len(objects),
            "records_extracted": total_records,
            "elapsed_ms": round(elapsed_ms, 3),
            "objects": objects,
        }

    def _elapsed_ms(self, started_at: float) -> float:
        return max(0.0, (self._monotonic() - started_at) * 1000.0)

    def _emit(
        self,
        event: LambdaEvent,
        request: LambdaExtractionRequest,
        playlist_id: str,
        spotify_snapshot_id: str | None,
        *,
        duration_ms: float,
        status: str,
        **details: Any,
    ) -> None:
        if self._telemetry is None:
            return
        self._telemetry.emit(
            event,
            pipeline_run_id=request.pipeline_run_id,
            playlist_id=playlist_id,
            snapshot_date=request.snapshot_date,
            spotify_snapshot_id=spotify_snapshot_id,
            duration_ms=duration_ms,
            status=status,
            **details,
        )


def lambda_handler(event: Mapping[str, Any], context: Any) -> dict[str, Any]:
    """AWS entrypoint using the environment-aware cached credential provider."""
    del context
    request = LambdaExtractionRequest.model_validate(event)
    bucket = _required_env("S3_BUCKET_NAME")
    auth = get_default_auth_client()
    telemetry = LambdaTelemetryLogger(configure_lambda_logger())

    def on_page(page: PageFetchTelemetry) -> None:
        telemetry.emit(
            LambdaEvent.PAGINATION_PAGE_FETCHED,
            pipeline_run_id=request.pipeline_run_id,
            playlist_id=page.playlist_id,
            snapshot_date=request.snapshot_date,
            spotify_snapshot_id=page.spotify_snapshot_id,
            duration_ms=page.duration_ms,
            status="RUNNING",
            page_number=page.page_number,
            offset=page.offset,
            records_in_page=page.records_in_page,
            total_records=page.total_records,
        )

    extractor = PlaylistItemsExtractor(auth, on_page=on_page)
    writer = S3BronzeWriter(bucket, _default_s3_client())
    try:
        return LambdaExtractorService(extractor, writer, telemetry=telemetry).run(request)
    except InvalidGrantException:
        invalidate_runtime_caches()
        raise


def _required_env(name: str, environ: Mapping[str, str] | None = None) -> str:
    env = os.environ if environ is None else environ
    value = env.get(name, "")
    if not isinstance(value, str) or not value.strip():
        raise LambdaConfigurationError(f"Missing required environment variable: {name}.")
    return value.strip()


def _default_s3_client() -> S3Client:
    try:
        boto3 = importlib.import_module("boto3")
    except ImportError:
        raise LambdaConfigurationError(
            "boto3 is unavailable; use the AWS Lambda runtime or package the AWS SDK."
        ) from None
    return boto3.client("s3")
