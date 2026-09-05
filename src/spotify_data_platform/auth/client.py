"""Refresh-token authentication with a monotonic, process-local token cache."""

import base64
import json
import math
import os
import time
from collections.abc import Callable, Mapping
from threading import Lock
from urllib.parse import urlencode
from urllib.request import Request

from spotify_data_platform._http import Response, TransportError, send


class SpotifyAuthException(Exception):
    """Authentication failed; messages never contain upstream bodies or secrets."""


class InvalidGrantException(SpotifyAuthException):
    """The operator must obtain a new refresh token through user consent."""


class SpotifyAuthClient:
    """Exchange externally supplied credentials; never perform interactive consent.

    Rotated refresh tokens are retained in memory. A future secret-store adapter
    must persist ``refresh_token`` securely before discarding this instance.
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        *,
        expiry_buffer: float = 60.0,
        timeout: float = 10.0,
        transport: Callable[[Request, float], Response] = send,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        for name, value in (
            ("client_id", client_id),
            ("client_secret", client_secret),
            ("refresh_token", refresh_token),
        ):
            if not isinstance(value, str) or not value.strip():
                raise SpotifyAuthException(f"Missing or invalid {name}.")
        if not math.isfinite(expiry_buffer) or expiry_buffer < 0:
            raise ValueError("expiry_buffer must be finite and non-negative.")
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be finite and positive.")
        self._client_id = client_id
        self._client_secret = client_secret
        self._refresh_token = refresh_token
        self._expiry_buffer = expiry_buffer
        self._timeout = timeout
        self._transport = transport
        self._clock = clock
        self._access_token: str | None = None
        self._refresh_at = 0.0
        self._invalid_grant = False
        self._lock = Lock()

    def __repr__(self) -> str:
        return "SpotifyAuthClient(credentials=<redacted>, tokens=<redacted>)"

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "SpotifyAuthClient":
        """Read an environment or injected mapping without loading .env files."""
        env = os.environ if environ is None else environ
        return cls(
            env.get("SPOTIFY_CLIENT_ID", ""),
            env.get("SPOTIFY_CLIENT_SECRET", ""),
            env.get("SPOTIFY_REFRESH_TOKEN", ""),
        )

    @property
    def refresh_token(self) -> str:
        """Return the current secret for explicit, secure persistence by the caller."""
        return self._refresh_token

    def get_access_token(self) -> str:
        """Reuse a valid token or refresh once under a lock before returning it."""
        with self._lock:
            if self._invalid_grant:
                raise InvalidGrantException("Refresh token rejected; reauthorization required.")
            if self._access_token is not None and self._clock() < self._refresh_at:
                return self._access_token
            return self._exchange()

    def _exchange(self) -> str:
        started_at = self._clock()
        credentials = base64.b64encode(f"{self._client_id}:{self._client_secret}".encode()).decode(
            "ascii"
        )
        request = Request(
            "https://accounts.spotify.com/api/token",
            data=urlencode(
                {"grant_type": "refresh_token", "refresh_token": self._refresh_token}
            ).encode(),
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            response = self._transport(request, self._timeout)
        except TransportError:
            raise SpotifyAuthException("Token endpoint could not be reached.") from None
        try:
            payload = json.loads(response.body)
        except (ValueError, UnicodeError):
            raise SpotifyAuthException("Token endpoint returned invalid JSON.") from None
        if not isinstance(payload, dict):
            raise SpotifyAuthException("Token endpoint returned an invalid object.")
        if response.status != 200:
            if payload.get("error") == "invalid_grant":
                self._invalid_grant = True
                self._access_token = None
                self._refresh_token = ""
                raise InvalidGrantException("Refresh token rejected; reauthorization required.")
            raise SpotifyAuthException(f"Token endpoint returned HTTP {response.status}.")
        token = payload.get("access_token")
        ttl = payload.get("expires_in")
        rotated = payload.get("refresh_token", self._refresh_token)
        if (
            not isinstance(token, str)
            or not token.strip()
            or any(char.isspace() for char in token)
            or str(payload.get("token_type", "")).lower() != "bearer"
            or type(ttl) is not int
            or ttl <= 0
            or not isinstance(rotated, str)
            or not rotated.strip()
        ):
            raise SpotifyAuthException("Token endpoint returned invalid token fields.")
        self._refresh_token = rotated
        # Account for request latency. Short-lived tokens use half their TTL as buffer.
        refresh_at = started_at + ttl - min(self._expiry_buffer, ttl / 2)
        if self._clock() >= started_at + ttl:
            raise SpotifyAuthException("Access token expired during the token exchange.")
        self._access_token = token
        self._refresh_at = refresh_at
        return token
