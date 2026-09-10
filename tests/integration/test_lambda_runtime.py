"""Exercise OAuth, extraction, lineage, and S3 publication with offline boundaries."""

import json
from datetime import UTC, date, datetime
from unittest.mock import Mock
from uuid import UUID

from spotify_data_platform._http import Response
from spotify_data_platform.auth import SpotifyAuthClient
from spotify_data_platform.extraction import PlaylistItemsExtractor
from spotify_data_platform.lambda_runtime import (
    LambdaExtractionRequest,
    LambdaExtractorService,
    S3BronzeWriter,
)

RUN_ID = UUID("123e4567-e89b-42d3-a456-426614174000")


def response(payload):
    return Response(200, json.dumps(payload).encode("utf-8"))


def test_real_auth_and_extractor_land_fixture_to_mocked_s3(load_spotify_fixture):
    playlist = load_spotify_fixture("sample_playlist_response.json")
    page = load_spotify_fixture("sample_playlist_items_single_page.json")
    token_transport = Mock(
        return_value=response(
            {
                "access_token": "synthetic-access",
                "token_type": "Bearer",
                "expires_in": 3600,
            }
        )
    )
    auth_clock = Mock(return_value=100.0)
    auth = SpotifyAuthClient(
        "synthetic-id",
        "synthetic-secret",
        "synthetic-refresh",
        transport=token_transport,
        clock=auth_clock,
    )
    api_transport = Mock(
        side_effect=[
            response(playlist),
            response(page),
            response({"snapshot_id": playlist["snapshot_id"]}),
        ]
    )
    extractor = PlaylistItemsExtractor(auth, transport=api_transport)
    s3 = Mock()
    writer = S3BronzeWriter("spotify-analytics-data-platform-bronze-us-east-1", s3)
    service = LambdaExtractorService(
        extractor,
        writer,
        now=lambda: datetime(2026, 9, 10, 13, 30, tzinfo=UTC),
        monotonic=Mock(side_effect=[50.0, 50.2]),
    )

    summary = service.run(
        LambdaExtractionRequest(
            playlist_ids=[playlist["id"]],
            pipeline_run_id=RUN_ID,
            snapshot_date=date(2026, 9, 1),
        )
    )

    assert summary["statusCode"] == 200
    assert summary["records_extracted"] == len(page["items"])
    assert token_transport.call_count == 1
    assert api_transport.call_count == 3
    put = s3.put_object.call_args.kwargs
    assert put["IfNoneMatch"] == "*"
    assert put["Key"].startswith("bronze/spotify/playlist_tracks/ingestion_date=2026-09-10/")
    assert json.loads(put["Body"]) == {
        "playlist_id": playlist["id"],
        "spotify_snapshot_id": playlist["snapshot_id"],
        "playlist": playlist,
        "pages": [page],
        "items": page["items"],
    }
