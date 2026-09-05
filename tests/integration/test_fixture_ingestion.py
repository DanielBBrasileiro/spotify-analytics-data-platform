"""Run checked-in source fixtures through extraction and opt-in parsing offline."""

import json
from unittest.mock import Mock

import pytest

from spotify_data_platform._http import Response
from spotify_data_platform.extraction import PlaylistItemsExtractor, SnapshotChangedException
from spotify_data_platform.extraction.items import ItemKind, parse_playlist_item


def http_response(payload):
    return Response(200, json.dumps(payload).encode())


def auth_provider():
    auth = Mock()
    auth.get_access_token.return_value = "synthetic-fixture-token"
    return auth


def test_multi_page_fixture_extraction_with_rate_limit_recovery(load_spotify_fixture):
    playlist = load_spotify_fixture("sample_playlist_response.json")
    first = load_spotify_fixture("sample_playlist_items_response.json")
    last = load_spotify_fixture("sample_playlist_items_last_page.json")
    limited = load_spotify_fixture("sample_rate_limit_error.json")
    version = {"snapshot_id": playlist["snapshot_id"]}
    transport = Mock(
        side_effect=[
            http_response(playlist),
            http_response(first),
            http_response(version),
            Response(429, json.dumps(limited).encode(), {"Retry-After": "3"}),
            http_response(last),
            http_response(version),
        ]
    )
    sleep = Mock()
    extractor = PlaylistItemsExtractor(
        auth_provider(), transport=transport, sleep=sleep, jitter=lambda: 0
    )
    result = extractor.extract(playlist["id"])
    assert result["playlist"] == playlist
    assert result["spotify_snapshot_id"] == playlist["snapshot_id"]
    assert result["pages"] == [first, last]
    assert result["items"] == first["items"] + last["items"]
    assert len(result["items"]) == 52
    assert all(parse_playlist_item(entry).kind is ItemKind.TRACK for entry in result["items"])
    assert result["items"][-1]["item"]["name"] == "Synthetic Track 52"
    sleep.assert_called_once_with(3)
    assert transport.call_args_list[3].args[0].full_url == last["href"]
    assert transport.call_args_list[4].args[0].full_url == last["href"]


def test_single_page_keeps_non_music_entries_and_source_order(load_spotify_fixture):
    playlist = load_spotify_fixture("sample_playlist_response.json")
    page = load_spotify_fixture("sample_playlist_items_single_page.json")
    transport = Mock(
        side_effect=[http_response(playlist), http_response(page), http_response(playlist)]
    )
    result = PlaylistItemsExtractor(auth_provider(), transport=transport).extract(playlist["id"])
    assert result["items"] == page["items"]
    assert [parse_playlist_item(entry).kind for entry in result["items"]] == [
        ItemKind.TRACK,
        ItemKind.TRACK,
        ItemKind.EPISODE,
        ItemKind.UNAVAILABLE,
    ]
    assert result["items"][1]["item"]["artists"][0]["id"] is None


def test_fixture_snapshot_mutation_aborts_before_fetching_tail(load_spotify_fixture):
    playlist = load_spotify_fixture("sample_playlist_response.json")
    first = load_spotify_fixture("sample_playlist_items_response.json")
    changed = {**playlist, "snapshot_id": "synthetic-snapshot-v2"}
    transport = Mock(
        side_effect=[http_response(playlist), http_response(first), http_response(changed)]
    )
    with pytest.raises(SnapshotChangedException):
        PlaylistItemsExtractor(auth_provider(), transport=transport).extract(playlist["id"])
    assert transport.call_count == 3
