"""Offline playlist pagination and snapshot consistency contracts."""

import copy
import json
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

import pytest

from spotify_data_platform._http import Response, TransportError
from spotify_data_platform.extraction import (
    PaginationException,
    PlaylistItemsExtractor,
    SnapshotChangedException,
    SpotifyExtractionException,
)

PLAYLIST_ID = "a" * 22


def response(payload, status=200, headers=None):
    return Response(status, json.dumps(payload).encode(), headers or {})


def metadata(snapshot="version-one"):
    return {"id": PLAYLIST_ID, "name": "Synthetic playlist", "snapshot_id": snapshot}


def page(offset=0, count=2, total=2):
    return {
        "offset": offset,
        "limit": 50,
        "total": total,
        "next": "https://api.spotify.com/next" if offset + count < total else None,
        "items": [
            {"added_at": None, "item": {"id": str(i), "type": "track"}}
            for i in range(offset, offset + count)
        ],
        "future_field": {"preserve": True},
    }


def make_extractor(responses, **kwargs):
    transport = Mock(side_effect=responses)
    auth = Mock()
    auth.get_access_token.return_value = "synthetic-access"
    return PlaylistItemsExtractor(auth, transport=transport, **kwargs), transport, auth


@pytest.mark.parametrize("total", [0, 1, 50, 51, 100, 123])
def test_pagination_boundaries_and_raw_preservation(total):
    pages = [page(offset, min(50, total - offset), total) for offset in range(0, max(total, 1), 50)]
    replies = [response(metadata())]
    for payload in pages:
        replies.extend([response(payload), response({"snapshot_id": "version-one"})])
    extractor, transport, auth = make_extractor(replies)
    result = extractor.extract(PLAYLIST_ID)
    assert result["playlist_id"] == PLAYLIST_ID
    assert result["spotify_snapshot_id"] == "version-one"
    assert result["playlist"] == metadata()
    assert result["pages"] == pages
    assert result["items"] == [item for payload in pages for item in payload["items"]]
    assert len(result["items"]) == total
    json.dumps(result)
    requests = [call.args[0] for call in transport.call_args_list]
    item_requests = [req for req in requests if "/items?" in req.full_url]
    assert [parse_qs(urlsplit(req.full_url).query) for req in item_requests] == [
        {"limit": ["50"], "offset": [str(payload["offset"])]} for payload in pages
    ]
    assert all(req.get_header("Authorization") == "Bearer synthetic-access" for req in requests)
    assert auth.get_access_token.call_count == len(requests)


def test_preserves_null_local_episode_and_duplicate_items():
    payload = page(count=4, total=4)
    payload["items"] = [
        None,
        {"item": None},
        {"is_local": True, "item": {"type": "episode"}},
        {"item": None},
    ]
    original = copy.deepcopy(payload)
    extractor, _, _ = make_extractor(
        [response(metadata()), response(payload), response(metadata())]
    )
    assert extractor.extract(PLAYLIST_ID)["items"] == original["items"]
    assert payload == original


@pytest.mark.parametrize("changed_after", [0, 1])
def test_mutation_aborts_without_partial_output(changed_after):
    replies = [response(metadata()), response(page(0, 50, 51))]
    if changed_after:
        replies += [response(metadata()), response(page(50, 1, 51))]
    replies += [response(metadata("version-two"))]
    extractor, transport, _ = make_extractor(replies)
    with pytest.raises(SnapshotChangedException):
        extractor.extract(PLAYLIST_ID)
    assert transport.call_count == len(replies)


@pytest.mark.parametrize(
    "changes",
    [
        {"items": {}},
        {"items": []},
        {"total": -1},
        {"total": True},
        {"total": "2"},
        {"offset": 1},
        {"offset": False},
        {"limit": 100},
        {"next": ""},
        {"next": 1},
        {"next": "unexpected-next"},
        {"total": 3},
        {"total": 1},
        {"items": [None] * 51},
    ],
)
def test_rejects_inconsistent_pagination(changes):
    payload = page()
    payload.update(changes)
    extractor, _, _ = make_extractor([response(metadata()), response(payload)])
    with pytest.raises(PaginationException):
        extractor.extract(PLAYLIST_ID)


def test_missing_next_and_changing_total_are_rejected():
    payload = page()
    del payload["next"]
    extractor, _, _ = make_extractor([response(metadata()), response(payload)])
    with pytest.raises(PaginationException):
        extractor.extract(PLAYLIST_ID)
    extractor, _, _ = make_extractor(
        [
            response(metadata()),
            response(page(0, 50, 51)),
            response(metadata()),
            response(page(50, 2, 52)),
        ]
    )
    with pytest.raises(PaginationException):
        extractor.extract(PLAYLIST_ID)


def test_page_limit_bounds_extraction():
    extractor, transport, _ = make_extractor(
        [response(metadata()), response(page(0, 50, 51)), response(metadata())], max_pages=1
    )
    with pytest.raises(PaginationException, match="page limit"):
        extractor.extract(PLAYLIST_ID)
    assert transport.call_count == 3


@pytest.mark.parametrize("payload", [{}, {"snapshot_id": None}, {"snapshot_id": ""}])
def test_missing_snapshot_id(payload):
    extractor, _, _ = make_extractor([response(payload)])
    with pytest.raises(SpotifyExtractionException, match="snapshot_id"):
        extractor.extract(PLAYLIST_ID)


@pytest.mark.parametrize(
    "reply",
    [
        response({}, 403),
        response({}, 401),
        response({}, 302),
        Response(200, b"invalid"),
        response([]),
        TransportError("synthetic-secret"),
    ],
)
def test_sanitized_endpoint_failures(reply):
    extractor, _, _ = make_extractor([reply])
    with pytest.raises(SpotifyExtractionException) as error:
        extractor.extract(PLAYLIST_ID)
    assert "synthetic-secret" not in str(error.value)


@pytest.mark.parametrize("playlist_id", ["", "../escape", "x?query=y", "a" * 21, None])
def test_invalid_playlist_id_never_dispatches(playlist_id):
    extractor, transport, _ = make_extractor([])
    with pytest.raises(ValueError):
        extractor.extract(playlist_id)
    transport.assert_not_called()


@pytest.mark.parametrize(
    "options",
    [
        {"timeout": 0},
        {"timeout": float("inf")},
        {"max_pages": 0},
        {"max_pages": True},
    ],
)
def test_invalid_configuration(options):
    with pytest.raises(ValueError):
        make_extractor([], **options)
