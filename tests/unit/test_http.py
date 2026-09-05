"""Exercise the real urllib adapter without opening network connections."""

from http.client import IncompleteRead
from io import BytesIO
from unittest.mock import MagicMock
from urllib.error import HTTPError, URLError
from urllib.request import Request

import pytest

from spotify_data_platform import _http


def test_success_and_redirect_policy(monkeypatch):
    opener = MagicMock()
    response = opener.open.return_value
    response.status, response.read.return_value, response.headers = 200, b"{}", {}
    factory = MagicMock(return_value=opener)
    monkeypatch.setattr(_http, "build_opener", factory)
    request = Request("https://example.invalid")
    assert _http.send(request, 7).body == b"{}"
    opener.open.assert_called_once_with(request, timeout=7)
    handler = factory.call_args.args[0]
    assert handler.redirect_request(request, None, 302, "", {}, "https://other.invalid") is None


def test_http_error_is_returned_and_closed(monkeypatch):
    stream = BytesIO(b"throttled")
    opener = MagicMock()
    opener.open.side_effect = HTTPError(
        "https://example.invalid", 429, "", {"Retry-After": "5"}, stream
    )
    monkeypatch.setattr(_http, "build_opener", lambda *_: opener)
    result = _http.send(Request("https://example.invalid"), 10)
    assert (result.status, result.body, result.headers["Retry-After"]) == (429, b"throttled", "5")
    assert stream.closed


@pytest.mark.parametrize("error", [URLError("secret"), OSError("secret"), ValueError("secret")])
def test_transport_failure_is_sanitized(monkeypatch, error):
    opener = MagicMock()
    opener.open.side_effect = error
    monkeypatch.setattr(_http, "build_opener", lambda *_: opener)
    with pytest.raises(_http.TransportError, match="HTTP transport failed"):
        _http.send(Request("https://example.invalid"), 10)


@pytest.mark.parametrize("status", [200, 429])
def test_interrupted_response_body_is_sanitized_and_closed(monkeypatch, status):
    opener = MagicMock()
    body = MagicMock()
    body.closed = False
    body.read.side_effect = IncompleteRead(b"synthetic-secret")
    if status == 429:
        opener.open.side_effect = HTTPError("https://example.invalid", status, "", {}, body)
    else:
        opener.open.return_value = body
        body.status = status
    monkeypatch.setattr(_http, "build_opener", lambda *_: opener)
    with pytest.raises(_http.TransportError, match="HTTP transport failed"):
        _http.send(Request("https://example.invalid"), 10)
    if status == 429:
        body.close.assert_called_once()
    else:
        body.__exit__.assert_called_once()
