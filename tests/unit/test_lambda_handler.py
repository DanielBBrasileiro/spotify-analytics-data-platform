"""Validated Lambda event and service orchestration contracts."""

import sys
import types
from datetime import UTC, date, datetime
from unittest.mock import Mock, patch
from uuid import UUID, uuid1

import pytest
from pydantic import ValidationError

from spotify_data_platform.auth import InvalidGrantException
from spotify_data_platform.extraction import PageFetchTelemetry
from spotify_data_platform.lambda_runtime import (
    LambdaConfigurationError,
    LambdaExtractionRequest,
    LambdaExtractorService,
)
from spotify_data_platform.lambda_runtime import handler as handler_module

RUN_ID = UUID("123e4567-e89b-42d3-a456-426614174000")
PLAYLIST_A = "a" * 22
PLAYLIST_B = "b" * 22


def request_payload(**changes):
    payload = {
        "playlist_ids": [PLAYLIST_A, PLAYLIST_B],
        "pipeline_run_id": str(RUN_ID),
        "snapshot_date": "2026-09-01",
    }
    payload.update(changes)
    return payload


def extracted(playlist_id, version, count):
    items = [{"item": {"id": str(index), "type": "track"}} for index in range(count)]
    return {
        "playlist_id": playlist_id,
        "spotify_snapshot_id": version,
        "playlist": {"id": playlist_id, "snapshot_id": version},
        "pages": [{"items": items}],
        "items": items,
    }


def test_request_validates_uuid_date_playlist_ids_and_uniqueness():
    request = LambdaExtractionRequest.model_validate(request_payload())
    assert request.pipeline_run_id == RUN_ID
    assert request.snapshot_date == date(2026, 9, 1)
    assert request.playlist_ids == [PLAYLIST_A, PLAYLIST_B]


@pytest.mark.parametrize(
    "changes",
    [
        {"playlist_ids": []},
        {"playlist_ids": ["short"]},
        {"playlist_ids": [PLAYLIST_A, PLAYLIST_A]},
        {"playlist_ids": [PLAYLIST_A] * 101},
        {"pipeline_run_id": str(uuid1())},
        {"pipeline_run_id": "invalid"},
        {"snapshot_date": "invalid"},
        {"unexpected": True},
    ],
)
def test_invalid_request_is_rejected(changes):
    with pytest.raises(ValidationError):
        LambdaExtractionRequest.model_validate(request_payload(**changes))


def test_service_writes_each_playlist_with_shared_run_and_business_date():
    extractor = Mock()
    extractor.extract.side_effect = [
        extracted(PLAYLIST_A, "version-a", 2),
        extracted(PLAYLIST_B, "version-b", 3),
    ]
    writer = Mock()
    writer.write.side_effect = ["s3://bucket/a.json", "s3://bucket/b.json"]
    timestamps = iter(
        [
            datetime(2026, 9, 10, 13, 0, tzinfo=UTC),
            datetime(2026, 9, 10, 13, 1, tzinfo=UTC),
        ]
    )
    monotonic = Mock(side_effect=[100.0, 100.125])
    service = LambdaExtractorService(
        extractor,
        writer,
        now=lambda: next(timestamps),
        monotonic=monotonic,
    )

    summary = service.run(LambdaExtractionRequest.model_validate(request_payload()))

    assert summary == {
        "statusCode": 200,
        "pipeline_run_id": str(RUN_ID),
        "snapshot_date": "2026-09-01",
        "playlist_count": 2,
        "records_extracted": 5,
        "elapsed_ms": 125.0,
        "objects": [
            {
                "playlist_id": PLAYLIST_A,
                "spotify_snapshot_id": "version-a",
                "records_extracted": 2,
                "snapshot_timestamp": "2026-09-10T13:00:00Z",
                "s3_uri": "s3://bucket/a.json",
            },
            {
                "playlist_id": PLAYLIST_B,
                "spotify_snapshot_id": "version-b",
                "records_extracted": 3,
                "snapshot_timestamp": "2026-09-10T13:01:00Z",
                "s3_uri": "s3://bucket/b.json",
            },
        ],
    }
    assert [call.args[0] for call in extractor.extract.call_args_list] == [PLAYLIST_A, PLAYLIST_B]
    first_metadata = writer.write.call_args_list[0].args[1]
    second_metadata = writer.write.call_args_list[1].args[1]
    assert first_metadata.pipeline_run_id == second_metadata.pipeline_run_id == RUN_ID
    assert first_metadata.snapshot_date == second_metadata.snapshot_date == date(2026, 9, 1)


def test_negative_clock_skew_never_reports_negative_latency():
    extractor = Mock()
    extractor.extract.return_value = extracted(PLAYLIST_A, "version", 0)
    writer = Mock(return_value="unused")
    writer.write.return_value = "s3://bucket/a.json"
    service = LambdaExtractorService(
        extractor,
        writer,
        now=lambda: datetime(2026, 9, 10, tzinfo=UTC),
        monotonic=Mock(side_effect=[10.0, 9.0]),
    )
    summary = service.run(
        LambdaExtractionRequest.model_validate(request_payload(playlist_ids=[PLAYLIST_A]))
    )
    assert summary["elapsed_ms"] == 0.0


def test_service_emits_success_lifecycle_without_changing_summary_contract():
    extractor = Mock()
    extractor.extract.return_value = extracted(PLAYLIST_A, "version-a", 2)
    writer = Mock()
    writer.write.return_value = "s3://bucket/a.json"
    telemetry = Mock()
    monotonic = Mock(side_effect=[100.0, 101.0, 101.05, 101.075, 101.1])
    service = LambdaExtractorService(
        extractor,
        writer,
        now=lambda: datetime(2026, 9, 10, 13, 0, tzinfo=UTC),
        monotonic=monotonic,
        telemetry=telemetry,
    )

    summary = service.run(
        LambdaExtractionRequest.model_validate(request_payload(playlist_ids=[PLAYLIST_A]))
    )

    assert summary["elapsed_ms"] == pytest.approx(1100.0)
    events = [call.args[0].value for call in telemetry.emit.call_args_list]
    assert events == ["EXTRACTION_START", "S3_WRITE_SUCCESS", "EXTRACTION_COMPLETE"]
    start = telemetry.emit.call_args_list[0].kwargs
    assert start["spotify_snapshot_id"] is None
    assert start["status"] == "RUNNING"
    write = telemetry.emit.call_args_list[1].kwargs
    assert write["spotify_snapshot_id"] == "version-a"
    assert write["records_extracted"] == 2
    assert write["s3_uri"] == "s3://bucket/a.json"
    complete = telemetry.emit.call_args_list[2].kwargs
    assert complete["status"] == "SUCCESS"
    assert complete["records_extracted"] == 2


def test_service_failure_telemetry_exposes_error_type_not_exception_message():
    extractor = Mock()
    extractor.extract.side_effect = RuntimeError("do-not-log-this-secret")
    telemetry = Mock()
    service = LambdaExtractorService(
        extractor,
        Mock(),
        monotonic=Mock(side_effect=[10.0, 10.1, 10.2]),
        telemetry=telemetry,
    )

    with pytest.raises(RuntimeError, match="do-not-log-this-secret"):
        service.run(
            LambdaExtractionRequest.model_validate(request_payload(playlist_ids=[PLAYLIST_A]))
        )

    assert [call.args[0].value for call in telemetry.emit.call_args_list] == [
        "EXTRACTION_START",
        "EXTRACTION_FAILED",
    ]
    failure = telemetry.emit.call_args_list[-1].kwargs
    assert failure["error_type"] == "RuntimeError"
    assert "do-not-log-this-secret" not in repr(failure)
    assert failure["spotify_snapshot_id"] is None
    assert failure["status"] == "FAILED"


def test_service_propagates_failure_without_telemetry_overhead():
    extractor = Mock()
    extractor.extract.side_effect = RuntimeError("synthetic failure")
    monotonic = Mock(return_value=10.0)
    service = LambdaExtractorService(extractor, Mock(), monotonic=monotonic)

    with pytest.raises(RuntimeError, match="synthetic failure"):
        service.run(
            LambdaExtractionRequest.model_validate(request_payload(playlist_ids=[PLAYLIST_A]))
        )

    monotonic.assert_called_once_with()


def test_required_env_strips_value_and_rejects_missing_or_blank():
    assert handler_module._required_env("NAME", {"NAME": " bucket "}) == "bucket"
    with pytest.raises(LambdaConfigurationError, match="NAME"):
        handler_module._required_env("NAME", {})
    with pytest.raises(LambdaConfigurationError, match="NAME"):
        handler_module._required_env("NAME", {"NAME": "   "})


def test_default_s3_client_uses_boto3_runtime_module(monkeypatch):
    client = object()
    boto3 = types.SimpleNamespace(client=Mock(return_value=client))
    monkeypatch.setitem(sys.modules, "boto3", boto3)
    assert handler_module._default_s3_client() is client
    boto3.client.assert_called_once_with("s3")


def test_default_s3_client_reports_missing_sdk_without_installing_it(monkeypatch):
    real_import = handler_module.importlib.import_module

    def fake_import(name):
        if name == "boto3":
            raise ImportError
        return real_import(name)

    monkeypatch.setattr(handler_module.importlib, "import_module", fake_import)
    with pytest.raises(LambdaConfigurationError, match="boto3 is unavailable"):
        handler_module._default_s3_client()


def test_lambda_handler_assembles_default_runtime_from_credential_provider(monkeypatch):
    auth = object()
    extractor = Mock()
    s3_client = object()
    writer = Mock()
    service = Mock()
    telemetry = Mock()
    service.run.return_value = {"statusCode": 200}

    monkeypatch.setenv("S3_BUCKET_NAME", "spotify-analytics-data-platform-bronze-us-east-1")
    with (
        patch.object(handler_module, "get_default_auth_client", return_value=auth) as auth_factory,
        patch.object(
            handler_module, "PlaylistItemsExtractor", return_value=extractor
        ) as extractor_factory,
        patch.object(handler_module, "_default_s3_client", return_value=s3_client),
        patch.object(handler_module, "S3BronzeWriter", return_value=writer) as writer_factory,
        patch.object(handler_module, "configure_lambda_logger", return_value=object()),
        patch.object(handler_module, "LambdaTelemetryLogger", return_value=telemetry),
        patch.object(
            handler_module, "LambdaExtractorService", return_value=service
        ) as service_factory,
    ):
        result = handler_module.lambda_handler(request_payload(playlist_ids=[PLAYLIST_A]), object())

    assert result == {"statusCode": 200}
    auth_factory.assert_called_once_with()
    extractor_factory.assert_called_once()
    assert extractor_factory.call_args.args == (auth,)
    assert callable(extractor_factory.call_args.kwargs["on_page"])
    writer_factory.assert_called_once_with(
        "spotify-analytics-data-platform-bronze-us-east-1", s3_client
    )
    service_factory.assert_called_once()
    assert service_factory.call_args.args == (extractor, writer)
    assert service_factory.call_args.kwargs["telemetry"] is telemetry
    assert service.run.call_args.args[0].pipeline_run_id == RUN_ID

    on_page = extractor_factory.call_args.kwargs["on_page"]
    on_page(
        PageFetchTelemetry(
            playlist_id=PLAYLIST_A,
            spotify_snapshot_id="version-a",
            page_number=1,
            offset=0,
            records_in_page=2,
            total_records=2,
            duration_ms=12.5,
        )
    )
    telemetry.emit.assert_called_once()
    assert telemetry.emit.call_args.args[0].value == "PAGINATION_PAGE_FETCHED"
    assert telemetry.emit.call_args.kwargs["pipeline_run_id"] == RUN_ID
    assert telemetry.emit.call_args.kwargs["spotify_snapshot_id"] == "version-a"
    assert telemetry.emit.call_args.kwargs["records_in_page"] == 2


def test_lambda_handler_rejects_missing_bucket_before_auth(monkeypatch):
    monkeypatch.delenv("S3_BUCKET_NAME", raising=False)
    with (
        patch.object(handler_module, "get_default_auth_client") as auth_factory,
        pytest.raises(LambdaConfigurationError, match="S3_BUCKET_NAME"),
    ):
        handler_module.lambda_handler(request_payload(playlist_ids=[PLAYLIST_A]), None)
    auth_factory.assert_not_called()


def test_invalid_event_is_rejected_before_runtime_factories(monkeypatch):
    monkeypatch.setenv("S3_BUCKET_NAME", "spotify-analytics-data-platform-bronze-us-east-1")
    with (
        patch.object(handler_module, "get_default_auth_client") as auth_factory,
        patch.object(handler_module, "_default_s3_client") as s3_factory,
        pytest.raises(ValidationError),
    ):
        handler_module.lambda_handler({"playlist_ids": []}, None)
    auth_factory.assert_not_called()
    s3_factory.assert_not_called()


def test_lambda_handler_invalidates_warm_credentials_after_invalid_grant(monkeypatch):
    auth = object()
    extractor = Mock()
    writer = Mock()
    service = Mock()
    service.run.side_effect = InvalidGrantException("reauthorization required")
    monkeypatch.setenv("S3_BUCKET_NAME", "spotify-analytics-data-platform-bronze-us-east-1")

    with (
        patch.object(handler_module, "get_default_auth_client", return_value=auth),
        patch.object(handler_module, "PlaylistItemsExtractor", return_value=extractor),
        patch.object(handler_module, "_default_s3_client", return_value=object()),
        patch.object(handler_module, "S3BronzeWriter", return_value=writer),
        patch.object(handler_module, "LambdaExtractorService", return_value=service),
        patch.object(handler_module, "invalidate_runtime_caches") as invalidate,
        pytest.raises(InvalidGrantException),
    ):
        handler_module.lambda_handler(request_payload(playlist_ids=[PLAYLIST_A]), None)

    invalidate.assert_called_once_with()
