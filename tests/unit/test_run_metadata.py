"""Validation and JSON round-trip contracts for ingestion run metadata."""

from datetime import UTC, date, datetime, timedelta, timezone
from uuid import UUID, uuid1

import pytest
from pydantic import ValidationError

from spotify_data_platform.ingestion import PipelineRunMetadata, RunStatus

RUN_ID = UUID("123e4567-e89b-42d3-a456-426614174000")
PLAYLIST_ID = "a" * 22


def metadata_payload(**changes):
    payload = {
        "pipeline_run_id": str(RUN_ID),
        "spotify_snapshot_id": "snapshot-v1",
        "playlist_id": PLAYLIST_ID,
        "snapshot_date": "2026-09-01",
        "snapshot_timestamp": "2026-09-09T23:30:45Z",
        "records_extracted": 52,
        "status": "SUCCESS",
    }
    payload.update(changes)
    return payload


def test_valid_metadata_distinguishes_business_date_from_capture_date():
    model = PipelineRunMetadata.model_validate(metadata_payload())
    assert model.pipeline_run_id == RUN_ID
    assert model.pipeline_run_id.version == 4
    assert model.snapshot_date == date(2026, 9, 1)
    assert model.snapshot_timestamp == datetime(2026, 9, 9, 23, 30, 45, tzinfo=UTC)
    assert model.snapshot_date != model.snapshot_timestamp.date()
    assert model.status is RunStatus.SUCCESS


def test_metadata_json_serialization_round_trips():
    model = PipelineRunMetadata.model_validate(metadata_payload())
    serialized = model.model_dump_json()
    assert PipelineRunMetadata.from_json(serialized) == model
    assert '"pipeline_run_id":"123e4567-e89b-42d3-a456-426614174000"' in serialized
    assert '"snapshot_date":"2026-09-01"' in serialized
    assert '"snapshot_timestamp":"2026-09-09T23:30:45Z"' in serialized


def test_offset_aware_timestamp_is_normalized_to_utc():
    local = timezone(timedelta(hours=-3))
    model = PipelineRunMetadata.model_validate(
        metadata_payload(snapshot_timestamp=datetime(2026, 9, 9, 20, 30, 45, tzinfo=local))
    )
    assert model.snapshot_timestamp == datetime(2026, 9, 9, 23, 30, 45, tzinfo=UTC)
    assert model.snapshot_timestamp.tzinfo is UTC


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("pipeline_run_id", str(uuid1())),
        ("pipeline_run_id", "not-a-uuid"),
        ("spotify_snapshot_id", ""),
        ("spotify_snapshot_id", "   "),
        ("playlist_id", "short"),
        ("playlist_id", "_" * 22),
        ("snapshot_date", "not-a-date"),
        ("snapshot_timestamp", "not-a-timestamp"),
        ("snapshot_timestamp", datetime(2026, 9, 9, 23, 30, 45)),
        ("records_extracted", -1),
        ("records_extracted", True),
        ("records_extracted", "52"),
        ("status", "DONE"),
    ],
)
def test_invalid_metadata_is_rejected(field, value):
    with pytest.raises(ValidationError):
        PipelineRunMetadata.model_validate(metadata_payload(**{field: value}))


def test_metadata_is_frozen_and_rejects_extra_fields():
    model = PipelineRunMetadata.model_validate(metadata_payload())
    with pytest.raises(ValidationError):
        model.records_extracted = 53
    with pytest.raises(ValidationError):
        PipelineRunMetadata.model_validate(metadata_payload(unexpected="field"))


@pytest.mark.parametrize("status", list(RunStatus))
def test_observability_status_values_are_supported(status):
    assert PipelineRunMetadata.model_validate(metadata_payload(status=status)).status is status
