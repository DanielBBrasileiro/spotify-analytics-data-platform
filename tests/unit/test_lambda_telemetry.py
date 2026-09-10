"""Structured JSON telemetry contracts for the Lambda ingestion runtime."""

import json
import logging
from datetime import UTC, date, datetime
from unittest.mock import Mock
from uuid import UUID

import pytest

from spotify_data_platform.lambda_runtime.telemetry import (
    JsonLogFormatter,
    LambdaEvent,
    LambdaTelemetryLogger,
    configure_lambda_logger,
)

RUN_ID = UUID("123e4567-e89b-42d3-a456-426614174000")
PLAYLIST_ID = "a" * 22


def test_json_formatter_emits_compact_single_line_structured_payload():
    record = logging.LogRecord("test", logging.INFO, __file__, 1, "ignored", (), None)
    record.telemetry = {"event": "EXTRACTION_COMPLETE", "label": "sintético 🎵"}

    rendered = JsonLogFormatter().format(record)

    assert "\n" not in rendered
    assert json.loads(rendered) == {
        "event": "EXTRACTION_COMPLETE",
        "label": "sintético 🎵",
    }


def test_json_formatter_safely_wraps_unstructured_records():
    record = logging.LogRecord("test", logging.WARNING, __file__, 1, "plain %s", ("message",), None)
    payload = json.loads(JsonLogFormatter().format(record))
    assert payload == {
        "event": "UNSTRUCTURED_LOG",
        "level": "WARNING",
        "message_suppressed": True,
    }
    assert "plain message" not in json.dumps(payload)


@pytest.mark.parametrize(
    ("status", "level"),
    [("RUNNING", logging.INFO), ("SUCCESS", logging.INFO), ("FAILED", logging.ERROR)],
)
def test_telemetry_logger_emits_mandatory_fields_with_sanitized_values(status, level):
    logger = Mock()
    telemetry = LambdaTelemetryLogger(
        logger,
        now=lambda: datetime(2026, 9, 10, 14, 30, 45, tzinfo=UTC),
    )

    telemetry.emit(
        LambdaEvent.EXTRACTION_FAILED if status == "FAILED" else LambdaEvent.EXTRACTION_START,
        pipeline_run_id=RUN_ID,
        playlist_id=PLAYLIST_ID,
        snapshot_date=date(2026, 9, 1),
        spotify_snapshot_id=None,
        duration_ms=-1.5,
        status=status,
        error_type="SyntheticError" if status == "FAILED" else None,
    )

    logger.log.assert_called_once()
    assert logger.log.call_args.args == (level, "")
    payload = logger.log.call_args.kwargs["extra"]["telemetry"]
    assert payload["timestamp"] == "2026-09-10T14:30:45Z"
    assert payload["pipeline_run_id"] == str(RUN_ID)
    assert payload["playlist_id"] == PLAYLIST_ID
    assert payload["spotify_snapshot_id"] is None
    assert payload["snapshot_date"] == "2026-09-01"
    assert payload["duration_ms"] == 0.0
    assert payload["status"] == status
    assert payload["level"] == ("ERROR" if status == "FAILED" else "INFO")
    assert payload["source"] == "spotify_web_api"
    assert payload["component"] == "lambda"
    assert payload["pipeline_version"]


def test_telemetry_details_cannot_override_correlation_fields():
    logger = Mock()
    telemetry = LambdaTelemetryLogger(
        logger,
        now=lambda: datetime(2026, 9, 10, 14, 30, tzinfo=UTC),
    )
    telemetry.emit(
        LambdaEvent.EXTRACTION_START,
        pipeline_run_id=RUN_ID,
        playlist_id=PLAYLIST_ID,
        snapshot_date=date(2026, 9, 1),
        spotify_snapshot_id=None,
        duration_ms=1.0,
        status="RUNNING",
        source="spoofed-source",
        component="spoofed-component",
    )
    payload = logger.log.call_args.kwargs["extra"]["telemetry"]
    assert payload["source"] == "spotify_web_api"
    assert payload["component"] == "lambda"
    assert payload["event"] == "EXTRACTION_START"


def test_configure_lambda_logger_is_idempotent_for_warm_containers():
    name = "spotify_data_platform.tests.telemetry.idempotent"
    logger = logging.getLogger(name)
    logger.handlers.clear()
    try:
        first = configure_lambda_logger(name)
        second = configure_lambda_logger(name)
        owned = [
            handler
            for handler in logger.handlers
            if getattr(handler, "_spotify_json_handler", False)
        ]
        assert first is second is logger
        assert len(owned) == 1
        assert isinstance(owned[0].formatter, JsonLogFormatter)
        assert logger.propagate is False
        assert logger.level == logging.INFO
    finally:
        logger.handlers.clear()


def test_configure_lambda_logger_removes_unowned_plain_text_handlers():
    name = "spotify_data_platform.tests.telemetry.owned"
    logger = logging.getLogger(name)
    logger.handlers.clear()
    unowned = logging.StreamHandler()
    logger.addHandler(unowned)
    try:
        configured = configure_lambda_logger(name)
        assert configured.handlers != [unowned]
        assert len(configured.handlers) == 1
        assert getattr(configured.handlers[0], "_spotify_json_handler", False) is True
        assert isinstance(configured.handlers[0].formatter, JsonLogFormatter)
    finally:
        logger.handlers.clear()
