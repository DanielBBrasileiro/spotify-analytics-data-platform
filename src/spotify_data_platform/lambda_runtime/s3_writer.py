"""Immutable Amazon S3 Bronze writer used by the Lambda extraction runtime."""

from collections.abc import Mapping
from typing import Any, Protocol

from spotify_data_platform.ingestion.bronze import (
    BronzeSnapshotValidationError,
    serialize_bronze_snapshot,
)
from spotify_data_platform.ingestion.models import PipelineRunMetadata
from spotify_data_platform.storage import build_bronze_playlist_key, build_bronze_playlist_uri


class S3Client(Protocol):
    """Minimal boto3 S3 client surface required by the Bronze writer."""

    def put_object(self, **kwargs: Any) -> Mapping[str, Any]:
        """Publish one immutable S3 object."""
        ...


class S3BronzeWriteError(Exception):
    """A validated Bronze snapshot could not be safely published to Amazon S3."""


class S3BronzeWriter:
    """Write complete snapshots to canonical S3 keys without allowing overwrites."""

    def __init__(self, bucket: str, client: S3Client) -> None:
        self._bucket = bucket
        self._client = client

    def write(self, snapshot: Mapping[str, Any], metadata: PipelineRunMetadata) -> str:
        """Publish UTF-8 JSON using S3's conditional create-only PutObject contract."""
        try:
            body = serialize_bronze_snapshot(snapshot, metadata)
            key = build_bronze_playlist_key(
                ingestion_date=metadata.snapshot_timestamp.date(),
                pipeline_run_id=metadata.pipeline_run_id,
                playlist_id=metadata.playlist_id,
            )
            uri = build_bronze_playlist_uri(
                self._bucket,
                ingestion_date=metadata.snapshot_timestamp.date(),
                pipeline_run_id=metadata.pipeline_run_id,
                playlist_id=metadata.playlist_id,
            )
        except (BronzeSnapshotValidationError, ValueError) as exc:
            raise S3BronzeWriteError(str(exc)) from exc

        request = {
            "Bucket": self._bucket,
            "Key": key,
            "Body": body,
            "ContentType": "application/json; charset=utf-8",
            "IfNoneMatch": "*",
            "ServerSideEncryption": "AES256",
        }
        for attempt in range(2):
            try:
                self._client.put_object(**request)
                return uri
            except Exception as exc:
                code = _aws_error_code(exc)
                if code in {"ConditionalRequestConflict", "409"} and attempt == 0:
                    continue
                if code in {"PreconditionFailed", "412"}:
                    raise S3BronzeWriteError(
                        "Bronze object already exists; immutable outputs are never overwritten."
                    ) from exc
                raise S3BronzeWriteError("Could not publish Bronze snapshot to S3.") from exc
        raise AssertionError("Unreachable S3 publication state.")  # pragma: no cover


def _aws_error_code(exc: Exception) -> str | None:
    response = getattr(exc, "response", None)
    if not isinstance(response, Mapping):
        return None
    error = response.get("Error")
    if not isinstance(error, Mapping):
        return None
    code = error.get("Code")
    return code if isinstance(code, str) else None
