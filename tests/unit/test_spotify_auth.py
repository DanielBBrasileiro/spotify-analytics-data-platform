"""Offline OAuth contract, cache, failure, and secret-redaction tests."""

import base64
import json
import traceback
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock
from urllib.parse import parse_qs

import pytest

from spotify_data_platform._http import Response, TransportError
from spotify_data_platform.auth import (
    InvalidGrantException,
    SpotifyAuthClient,
    SpotifyAuthException,
)


def token_response(**changes):
    payload = {"access_token": "synthetic-access", "token_type": "Bearer", "expires_in": 3600}
    payload.update(changes)
    return Response(200, json.dumps(payload).encode())


@pytest.fixture
def setup_client():
    transport = Mock(return_value=token_response())
    clock = Mock(return_value=100.0)
    client = SpotifyAuthClient(
        "synthetic-id", "synthetic-secret", "synthetic-refresh", transport=transport, clock=clock
    )
    return client, transport, clock


def test_exchange_contract_and_cache(setup_client):
    client, transport, clock = setup_client
    assert client.get_access_token() == "synthetic-access"
    request, timeout = transport.call_args.args
    assert request.full_url == "https://accounts.spotify.com/api/token"
    assert request.method == "POST"
    assert timeout == 10
    assert request.get_header("Content-type") == "application/x-www-form-urlencoded"
    assert (
        request.get_header("Authorization")
        == "Basic " + base64.b64encode(b"synthetic-id:synthetic-secret").decode()
    )
    assert parse_qs(request.data.decode()) == {
        "grant_type": ["refresh_token"],
        "refresh_token": ["synthetic-refresh"],
    }
    clock.return_value = 3639.99
    assert client.get_access_token() == "synthetic-access"
    assert transport.call_count == 1
    clock.return_value = 3640.0
    transport.return_value = token_response(access_token="synthetic-next")
    assert client.get_access_token() == "synthetic-next"
    assert transport.call_count == 2


def test_concurrent_callers_share_cache(setup_client):
    client, transport, _ = setup_client
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert (
            list(pool.map(lambda _: client.get_access_token(), range(20)))
            == ["synthetic-access"] * 20
        )
    transport.assert_called_once()


def test_rotation_is_used_on_next_exchange(setup_client):
    client, transport, clock = setup_client
    transport.return_value = token_response(refresh_token="synthetic-rotated")
    client.get_access_token()
    assert client.refresh_token == "synthetic-rotated"
    clock.return_value = 4000
    transport.return_value = token_response()
    client.get_access_token()
    assert parse_qs(transport.call_args.args[0].data.decode())["refresh_token"] == [
        "synthetic-rotated"
    ]
    assert client.refresh_token == "synthetic-rotated"


def test_short_lived_token_and_request_latency(setup_client):
    client, transport, clock = setup_client
    transport.return_value = token_response(expires_in=30)
    client.get_access_token()
    clock.return_value = 114
    client.get_access_token()
    assert transport.call_count == 1
    clock.return_value = 115
    client.get_access_token()
    assert transport.call_count == 2
    clock.side_effect = [200, 200, 231]
    with pytest.raises(SpotifyAuthException, match="expired during"):
        client.get_access_token()


@pytest.mark.parametrize(
    "changes",
    [
        {"access_token": ""},
        {"access_token": None},
        {"access_token": "bad\r\ntoken"},
        {"token_type": "Basic"},
        {"expires_in": 0},
        {"expires_in": -1},
        {"expires_in": True},
        {"expires_in": "3600"},
        {"expires_in": 1.5},
        {"refresh_token": ""},
        {"refresh_token": None},
    ],
)
def test_invalid_token_fields_are_not_cached(setup_client, changes):
    client, transport, _ = setup_client
    transport.return_value = token_response(**changes)
    with pytest.raises(SpotifyAuthException, match="invalid token fields"):
        client.get_access_token()
    transport.return_value = token_response()
    assert client.get_access_token() == "synthetic-access"
    assert transport.call_count == 2


@pytest.mark.parametrize("body", [b"not-json", b"\xff", b"[]", b"null"])
def test_malformed_response(setup_client, body):
    client, transport, _ = setup_client
    transport.return_value = Response(200, body)
    with pytest.raises(SpotifyAuthException):
        client.get_access_token()


def test_invalid_grant_stops_retries_and_discards_token(setup_client):
    client, transport, _ = setup_client
    transport.return_value = Response(400, b'{"error":"invalid_grant"}')
    for _ in range(2):
        with pytest.raises(InvalidGrantException, match="reauthorization"):
            client.get_access_token()
    assert client.refresh_token == ""
    transport.assert_called_once()


def test_errors_and_representations_do_not_disclose_secrets(setup_client, caplog):
    client, transport, _ = setup_client
    for result in [
        Response(401, b'{"error":"synthetic-secret"}'),
        TransportError("synthetic-secret"),
    ]:
        transport.side_effect = [result]
        with pytest.raises(SpotifyAuthException) as error:
            client.get_access_token()
        rendered = "".join(traceback.format_exception(error.value))
        assert "synthetic-secret" not in rendered
    assert "synthetic-" not in repr(client) + repr(token_response()) + caplog.text


def test_environment_mapping_and_process_environment(monkeypatch):
    env = {
        "SPOTIFY_CLIENT_ID": "fake-id",
        "SPOTIFY_CLIENT_SECRET": "fake-secret",
        "SPOTIFY_REFRESH_TOKEN": "fake-refresh",
    }
    assert SpotifyAuthClient.from_env(env).refresh_token == "fake-refresh"
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    assert SpotifyAuthClient.from_env().refresh_token == "fake-refresh"
    with pytest.raises(SpotifyAuthException):
        SpotifyAuthClient.from_env({})


@pytest.mark.parametrize("field", range(3))
@pytest.mark.parametrize("value", ["", "  ", None])
def test_missing_credentials(field, value):
    credentials = ["fake-id", "fake-secret", "fake-refresh"]
    credentials[field] = value
    with pytest.raises(SpotifyAuthException):
        SpotifyAuthClient(*credentials)


@pytest.mark.parametrize(
    "options",
    [
        {"expiry_buffer": -1},
        {"expiry_buffer": float("nan")},
        {"timeout": 0},
        {"timeout": float("inf")},
    ],
)
def test_invalid_timing_configuration(options):
    with pytest.raises(ValueError):
        SpotifyAuthClient("fake-id", "fake-secret", "fake-refresh", **options)
