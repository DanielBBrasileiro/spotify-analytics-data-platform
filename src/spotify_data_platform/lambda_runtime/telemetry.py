"""Single-line JSON lifecycle telemetry for the AWS Lambda ingestion runtime."""

import json
import logging
from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from spotify_data_platform import __version__


class LambdaEvent(StrEnum):
    """Stable lifecycle event names emitted by the Lambda ingestion runtime."""

    EXTRACTION_START = "EXTRACTION_START"
    PAGINATION_PAGE_FETCHED = "PAGINATION_PAGE_FETCHED"
    S3_WRITE_SUCCESS = "S3_WRITE_SUCCESS"
    EXTRACTION_COMPLETE = "EXTRACTION_COMPLETE"
    EXTRACTION_FAILED = "EXTRACTION_FAILED"


class JsonLogFormatter(logging.Formatter):
    """Render the structured payload attached by ``LambdaTelemetryLogger`` as JSON."""

    def format(self, record: logging.LogRecord) -> str:
        payload = getattr(record, "telemetry", None)
        if not isinstance(payload, Mapping):
            payload = {
                "event": "UNSTRUCTURED_LOG",
                "level": record.levelname,
                "message_suppressed": True,
            }
        return json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
            allow_nan=False,
        )


class LambdaTelemetryLogger:
    """Emit sanitized lifecycle records with stable cross-event correlation fields."""

    def __init__(
        self,
        logger: logging.Logger,
        *,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._logger = logger
        self._now = now

    def emit(
        self,
        event: LambdaEvent,
        *,
        pipeline_run_id: UUID,
        playlist_id: str,
        snapshot_date: date,
        spotify_snapshot_id: str | None,
        duration_ms: float,
        status: str,
        **details: Any,
    ) -> None:
        """Write one single-line JSON event without raw payloads or credentials."""
        timestamp = self._now().astimezone(UTC).isoformat().replace("+00:00", "Z")
        payload: dict[str, Any] = dict(details)
        payload.update(
            {
                "timestamp": timestamp,
                "event": event.value,
                "level": "INFO" if status != "FAILED" else "ERROR",
                "source": "spotify_web_api",
                "component": "lambda",
                "pipeline_version": __version__,
                "pipeline_run_id": str(pipeline_run_id),
                "playlist_id": playlist_id,
                "spotify_snapshot_id": spotify_snapshot_id,
                "snapshot_date": snapshot_date.isoformat(),
                "duration_ms": round(max(0.0, duration_ms), 3),
                "status": status,
            }
        )
        self._logger.log(
            logging.ERROR if status == "FAILED" else logging.INFO,
            "",
            extra={"telemetry": payload},
        )


def configure_lambda_logger(name: str = "spotify_data_platform.lambda") -> logging.Logger:
    """Own one JSON stream handler on the dedicated warm-container logger."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    handler = next(
        (
            existing
            for existing in logger.handlers
            if getattr(existing, "_spotify_json_handler", False)
        ),
        None,
    )
    if handler is None:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonLogFormatter())
        handler._spotify_json_handler = True  # type: ignore[attr-defined]
    logger.handlers[:] = [handler]
    return logger
