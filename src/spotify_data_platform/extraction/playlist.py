"""Read raw playlist pages, rejecting incomplete or changing observations."""

import json
import math
import re
from collections.abc import Callable
from typing import Any, Protocol, TypedDict
from urllib.parse import urlencode
from urllib.request import Request

from spotify_data_platform._http import Response, TransportError, send


class TokenProvider(Protocol):
    """Minimal authentication boundary, implemented by SpotifyAuthClient."""

    def get_access_token(self) -> str:
        """Return a currently usable bearer token."""
        ...


class PlaylistSnapshot(TypedDict):
    """JSON-serializable observation; source payloads remain untransformed."""

    playlist_id: str
    spotify_snapshot_id: str
    playlist: dict[str, Any]
    pages: list[dict[str, Any]]
    items: list[Any]


class SpotifyExtractionException(Exception):
    """An extraction failed without producing a partial snapshot."""


class PaginationException(SpotifyExtractionException):
    """Pagination metadata cannot establish a complete, bounded traversal."""


class SnapshotChangedException(SpotifyExtractionException):
    """The playlist changed; the caller must restart the entire extraction."""


class PlaylistItemsExtractor:
    """Fetch all pages into memory and return only after version verification.

    Spotify does not expose a pinned read transaction. Version checks detect
    observed changes, but are not a server-side atomicity guarantee.
    """

    def __init__(
        self,
        auth: TokenProvider,
        *,
        timeout: float = 10.0,
        max_pages: int = 1000,
        transport: Callable[[Request, float], Response] = send,
    ) -> None:
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be finite and positive.")
        if type(max_pages) is not int or max_pages <= 0:
            raise ValueError("max_pages must be a positive integer.")
        self._auth = auth
        self._timeout = timeout
        self._max_pages = max_pages
        self._transport = transport

    def extract(self, playlist_id: str) -> PlaylistSnapshot:
        """Preserve item order, nulls, duplicates, and unknown source fields."""
        if not isinstance(playlist_id, str) or not re.fullmatch(r"[A-Za-z0-9]{22}", playlist_id):
            raise ValueError("playlist_id must be a 22-character Spotify base62 ID.")
        base_url = f"https://api.spotify.com/v1/playlists/{playlist_id}"
        playlist = self._get_json(base_url)
        snapshot_id = self._snapshot_id(playlist)
        pages: list[dict[str, Any]] = []
        items: list[Any] = []
        total: int | None = None
        while True:
            if len(pages) >= self._max_pages:
                raise PaginationException("Configured page limit exceeded.")
            offset = len(items)
            payload = self._get_json(
                base_url + "/items?" + urlencode({"limit": 50, "offset": offset})
            )
            total = self._validate_page(payload, offset, total)
            current = self._get_json(base_url + "?fields=snapshot_id")
            if self._snapshot_id(current) != snapshot_id:
                raise SnapshotChangedException(
                    "Playlist changed during extraction; restart required."
                )
            pages.append(payload)
            items.extend(payload["items"])
            if len(items) == total:
                return {
                    "playlist_id": playlist_id,
                    "spotify_snapshot_id": snapshot_id,
                    "playlist": playlist,
                    "pages": pages,
                    "items": items,
                }

    @staticmethod
    def _snapshot_id(payload: dict[str, Any]) -> str:
        value = payload.get("snapshot_id")
        if not isinstance(value, str) or not value.strip():
            raise SpotifyExtractionException("Playlist response lacks a valid snapshot_id.")
        return value

    @staticmethod
    def _validate_page(payload: dict[str, Any], offset: int, expected_total: int | None) -> int:
        batch, total = payload.get("items"), payload.get("total")
        if (
            not isinstance(batch, list)
            or len(batch) > 50
            or type(total) is not int
            or total < 0
            or type(payload.get("offset")) is not int
            or payload["offset"] != offset
            or type(payload.get("limit")) is not int
            or payload["limit"] != 50
            or "next" not in payload
            or (
                payload["next"] is not None
                and (not isinstance(payload["next"], str) or not payload["next"].strip())
            )
        ):
            raise PaginationException("Invalid playlist pagination metadata.")
        end = offset + len(batch)
        if (
            (expected_total is not None and total != expected_total)
            or end > total
            or (end < total and (not batch or payload["next"] is None))
            or (end == total and payload["next"] is not None)
        ):
            raise PaginationException("Inconsistent playlist pagination metadata.")
        # The next URL is never followed: construct offsets against our fixed API origin.
        return total

    def _get_json(self, url: str) -> dict[str, Any]:
        request = Request(
            url,
            headers={
                "Authorization": f"Bearer {self._auth.get_access_token()}",
                "Accept": "application/json",
            },
        )
        try:
            response = self._transport(request, self._timeout)
        except TransportError:
            raise SpotifyExtractionException("Spotify API could not be reached.") from None
        if response.status != 200:
            raise SpotifyExtractionException(f"Spotify API returned HTTP {response.status}.")
        try:
            payload = json.loads(response.body)
        except (ValueError, UnicodeError):
            raise SpotifyExtractionException("Spotify API returned invalid JSON.") from None
        if not isinstance(payload, dict):
            raise SpotifyExtractionException("Spotify API returned an invalid object.")
        return payload
