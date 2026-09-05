"""Run real auth, extraction, and HTTP adapters over a scripted offline server."""

import json
from io import BytesIO
from unittest.mock import Mock
from urllib.error import HTTPError
from urllib.parse import parse_qs

from spotify_data_platform import _http
from spotify_data_platform.auth import SpotifyAuthClient
from spotify_data_platform.extraction import PlaylistItemsExtractor


class FakeHTTPResponse(BytesIO):
    status = 200
    headers = {"Content-Type": "application/json"}

    def __init__(self, payload):
        super().__init__(json.dumps(payload).encode())


def test_real_clients_refresh_during_rate_limit_recovery(monkeypatch):
    now = [0.0]
    requests = []
    responses = []
    token_url = "https://accounts.spotify.com/api/token"
    base_url = "https://api.spotify.com/v1/playlists/" + "a" * 22
    script = iter(
        [
            (
                token_url,
                {
                    "access_token": "first-token",
                    "expires_in": 120,
                    "token_type": "Bearer",
                    "refresh_token": "rotated-token",
                },
            ),
            (base_url, {"snapshot_id": "stable-version"}),
            (base_url + "/items?limit=50&offset=0", None),
            (
                token_url,
                {"access_token": "second-token", "expires_in": 3600, "token_type": "Bearer"},
            ),
            (
                base_url + "/items?limit=50&offset=0",
                {
                    "items": [{"item": {"type": "track", "id": "synthetic-track"}}],
                    "offset": 0,
                    "limit": 50,
                    "next": None,
                    "total": 1,
                },
            ),
            (base_url + "?fields=snapshot_id", {"snapshot_id": "stable-version"}),
        ]
    )

    def open_request(request, *, timeout):
        expected_url, payload = next(script)
        assert request.full_url == expected_url
        assert timeout == 10
        requests.append(request)
        if payload is None:
            body = BytesIO(b"rate limited")
            responses.append(body)
            raise HTTPError(request.full_url, 429, "", {"Retry-After": "120"}, body)
        result = FakeHTTPResponse(payload)
        responses.append(result)
        return result

    def advance(seconds):
        assert seconds == 120
        now[0] += seconds

    monkeypatch.setattr(_http, "build_opener", lambda *_: Mock(open=open_request))
    auth = SpotifyAuthClient(
        "synthetic-id", "synthetic-secret", "initial-token", clock=lambda: now[0]
    )
    extractor = PlaylistItemsExtractor(auth, sleep=advance, jitter=lambda: 0)
    snapshot = extractor.extract("a" * 22)
    assert snapshot["items"][0]["item"]["id"] == "synthetic-track"
    assert snapshot["spotify_snapshot_id"] == "stable-version"
    assert parse_qs(requests[3].data.decode())["refresh_token"] == ["rotated-token"]
    assert requests[2].get_header("Authorization") == "Bearer first-token"
    assert requests[4].get_header("Authorization") == "Bearer second-token"
    assert all(response.closed for response in responses)
    assert next(script, None) is None
