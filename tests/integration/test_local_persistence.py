"""Exercise fixture extraction through the local Bronze persistence boundary."""

import json
from datetime import UTC, date, datetime
from unittest.mock import Mock
from uuid import UUID

from spotify_data_platform._http import Response
from spotify_data_platform.extraction import PlaylistItemsExtractor
from spotify_data_platform.ingestion import LocalBronzeWriter, PipelineRunMetadata, RunStatus

RUN_ID = UUID("123e4567-e89b-42d3-a456-426614174000")


def response(payload):
    return Response(200, json.dumps(payload).encode())


def test_checked_in_fixture_extracts_and_lands_unchanged(tmp_path, load_spotify_fixture):
    playlist = load_spotify_fixture("sample_playlist_response.json")
    page = load_spotify_fixture("sample_playlist_items_single_page.json")
    auth = Mock()
    auth.get_access_token.return_value = "synthetic-token"
    transport = Mock(
        side_effect=[
            response(playlist),
            response(page),
            response({"snapshot_id": playlist["snapshot_id"]}),
        ]
    )
    extracted = PlaylistItemsExtractor(auth, transport=transport).extract(playlist["id"])
    run = PipelineRunMetadata(
        pipeline_run_id=RUN_ID,
        spotify_snapshot_id=extracted["spotify_snapshot_id"],
        playlist_id=extracted["playlist_id"],
        snapshot_date=date(2026, 9, 1),
        snapshot_timestamp=datetime(2026, 9, 9, 23, 45, tzinfo=UTC),
        records_extracted=len(extracted["items"]),
        status=RunStatus.SUCCESS,
    )

    destination = LocalBronzeWriter(tmp_path).write(extracted, run)

    assert json.loads(destination.read_text(encoding="utf-8")) == extracted
    assert destination.relative_to(tmp_path).as_posix() == (
        "bronze/spotify/playlist_tracks/ingestion_date=2026-09-09/"
        f"run_id={RUN_ID}/playlist_{playlist['id']}.json"
    )
    assert transport.call_count == 3
