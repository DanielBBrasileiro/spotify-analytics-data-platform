"""Immutable S3 Bronze publication contracts for the Lambda runtime."""

import json
from datetime import UTC, date, datetime
from unittest.mock import Mock
from uuid import UUID

import pytest

from spotify_data_platform.ingestion import PipelineRunMetadata, RunStatus
from spotify_data_platform.lambda_runtime import S3BronzeWriteError, S3BronzeWriter

RUN_ID = UUID("123e4567-e89b-42d3-a456-426614174000")
PLAYLIST_ID = "a" * 22
BUCKET = "spotify-analytics-data-platform-bronze-us-east-1"


def metadata(**changes):
    values = {
        "pipeline_run_id": RUN_ID,
        "spotify_snapshot_id": "snapshot-v1",
        "playlist_id": PLAYLIST_ID,
        "snapshot_date": date(2026, 9, 1),
        "snapshot_timestamp": datetime(2026, 9, 10, 12, 30, tzinfo=UTC),
        "records_extracted": 2,
        "status": RunStatus.SUCCESS,
    }
    values.update(changes)
    return PipelineRunMetadata(**values)


def snapshot():
    return {
        "playlist_id": PLAYLIST_ID,
        "spotify_snapshot_id": "snapshot-v1",
        "playlist": {"id": PLAYLIST_ID, "snapshot_id": "snapshot-v1", "name": "Sintética 🎵"},
        "pages": [{"items": [None, {"item": {"type": "track"}}]}],
        "items": [None, {"item": {"type": "track"}}],
    }


def test_put_object_uses_canonical_immutable_contract():
    client = Mock()
    writer = S3BronzeWriter(BUCKET, client)

    uri = writer.write(snapshot(), metadata())

    assert uri == (
        f"s3://{BUCKET}/bronze/spotify/playlist_tracks/ingestion_date=2026-09-10/"
        f"run_id={RUN_ID}/playlist_{PLAYLIST_ID}.json"
    )
    kwargs = client.put_object.call_args.kwargs
    assert kwargs["Bucket"] == BUCKET
    assert kwargs["Key"].endswith(f"run_id={RUN_ID}/playlist_{PLAYLIST_ID}.json")
    assert kwargs["IfNoneMatch"] == "*"
    assert kwargs["ServerSideEncryption"] == "AES256"
    assert kwargs["ContentType"] == "application/json; charset=utf-8"
    assert json.loads(kwargs["Body"].decode("utf-8")) == snapshot()


def test_invalid_snapshot_is_rejected_before_s3_call():
    client = Mock()
    raw = snapshot()
    raw["spotify_snapshot_id"] = "different"

    with pytest.raises(S3BronzeWriteError, match="spotify_snapshot_id"):
        S3BronzeWriter(BUCKET, client).write(raw, metadata())

    client.put_object.assert_not_called()


def test_invalid_bucket_is_wrapped_before_s3_call():
    client = Mock()
    with pytest.raises(S3BronzeWriteError, match="bucket"):
        S3BronzeWriter("Bad_Bucket", client).write(snapshot(), metadata())
    client.put_object.assert_not_called()


class AwsError(Exception):
    def __init__(self, code):
        super().__init__("synthetic aws failure")
        self.response = {"Error": {"Code": code}}


def test_precondition_failure_reports_immutable_collision():
    client = Mock()
    client.put_object.side_effect = AwsError("PreconditionFailed")
    with pytest.raises(S3BronzeWriteError, match="never overwritten"):
        S3BronzeWriter(BUCKET, client).write(snapshot(), metadata())


def test_numeric_precondition_code_is_also_treated_as_collision():
    client = Mock()
    client.put_object.side_effect = AwsError("412")
    with pytest.raises(S3BronzeWriteError, match="never overwritten"):
        S3BronzeWriter(BUCKET, client).write(snapshot(), metadata())


@pytest.mark.parametrize("code", ["ConditionalRequestConflict", "409"])
def test_conditional_conflict_is_retried_once(code):
    client = Mock()
    client.put_object.side_effect = [AwsError(code), {"ETag": "synthetic"}]
    uri = S3BronzeWriter(BUCKET, client).write(snapshot(), metadata())
    assert uri.startswith(f"s3://{BUCKET}/")
    assert client.put_object.call_count == 2


def test_repeated_conditional_conflict_fails_after_one_retry():
    client = Mock()
    client.put_object.side_effect = [
        AwsError("ConditionalRequestConflict"),
        AwsError("ConditionalRequestConflict"),
    ]
    with pytest.raises(S3BronzeWriteError, match="Could not publish"):
        S3BronzeWriter(BUCKET, client).write(snapshot(), metadata())
    assert client.put_object.call_count == 2


def test_generic_s3_failure_is_sanitized():
    client = Mock()
    client.put_object.side_effect = RuntimeError("secret upstream details")
    with pytest.raises(S3BronzeWriteError, match="Could not publish") as exc_info:
        S3BronzeWriter(BUCKET, client).write(snapshot(), metadata())
    assert "secret upstream details" not in str(exc_info.value)


@pytest.mark.parametrize(
    "response",
    [None, [], {}, {"Error": []}, {"Error": {}}, {"Error": {"Code": 412}}],
)
def test_malformed_aws_error_response_falls_back_to_generic_failure(response):
    client = Mock()
    error = RuntimeError("synthetic")
    error.response = response
    client.put_object.side_effect = error
    with pytest.raises(S3BronzeWriteError, match="Could not publish"):
        S3BronzeWriter(BUCKET, client).write(snapshot(), metadata())
