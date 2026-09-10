"""Read raw playlist pages, rejecting incomplete or changing observations."""

import json
import math
import random
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
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


@dataclass(frozen=True)
class PageFetchTelemetry:
    """Sanitized progress emitted after one page passes source-version validation."""

    playlist_id: str
    spotify_snapshot_id: str
    page_number: int
    offset: int
    records_in_page: int
    total_records: int
    duration_ms: float


class SpotifyExtractionException(Exception):
    """An extraction failed without producing a partial snapshot."""


class PaginationException(SpotifyExtractionException):
    """Pagination metadata cannot establish a complete, bounded traversal."""


class SnapshotChangedException(SpotifyExtractionException):
    """The playlist changed; the caller must restart the entire extraction."""


class RateLimitExceededException(SpotifyExtractionException):
    """Throttling exceeded the request retry or wait budget."""


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
        max_retries: int = 5,
        max_retry_wait: float = 300.0,
        transport: Callable[[Request, float], Response] = send,
        sleep: Callable[[float], None] = time.sleep,
        jitter: Callable[[], float] = random.random,
        on_page: Callable[[PageFetchTelemetry], None] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be finite and positive.")
        if type(max_pages) is not int or max_pages <= 0:
            raise ValueError("max_pages must be a positive integer.")
        if type(max_retries) is not int or max_retries < 0:
            raise ValueError("max_retries must be a non-negative integer.")
        if not math.isfinite(max_retry_wait) or max_retry_wait <= 0:
            raise ValueError("max_retry_wait must be finite and positive.")
        self._auth = auth
        self._timeout = timeout
        self._max_pages = max_pages
        self._transport = transport
        self._max_retries = max_retries
        self._max_retry_wait = max_retry_wait
        self._sleep = sleep
        self._jitter = jitter
        self._on_page = on_page
        self._clock = clock

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
            page_started_at = self._clock()
            payload = self._get_json(
                base_url + "/items?" + urlencode({"limit": 50, "offset": offset})
            )
            total = self._validate_page(payload, offset, total)
            current = self._get_json(base_url + "?fields=snapshot_id")
            if self._snapshot_id(current) != snapshot_id:
                raise SnapshotChangedException(
                    "Playlist changed during extraction; restart required."
                )
            if self._on_page is not None:
                self._on_page(
                    PageFetchTelemetry(
                        playlist_id=playlist_id,
                        spotify_snapshot_id=snapshot_id,
                        page_number=len(pages) + 1,
                        offset=offset,
                        records_in_page=len(payload["items"]),
                        total_records=total,
                        duration_ms=max(0.0, (self._clock() - page_started_at) * 1000.0),
                    )
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
        response = self._request_with_retries(url)
        try:
            payload = json.loads(response.body)
        except (ValueError, UnicodeError):
            raise SpotifyExtractionException("Spotify API returned invalid JSON.") from None
        if not isinstance(payload, dict):
            raise SpotifyExtractionException("Spotify API returned an invalid object.")
        return payload

    def _request_with_retries(self, url: str) -> Response:
        for attempt in range(self._max_retries + 1):
            response = self._request_once(url)
            if response.status == 200:
                return response
            throttled = response.status == 429
            if not throttled and not 500 <= response.status <= 599:
                raise SpotifyExtractionException(f"Spotify API returned HTTP {response.status}.")
            error_type = RateLimitExceededException if throttled else SpotifyExtractionException
            if attempt == self._max_retries:
                raise error_type(f"Spotify API retry budget exhausted (HTTP {response.status}).")
            delay = min(2 ** min(attempt, 6), 60) + self._jitter()
            retry_after = next(
                (
                    value
                    for name, value in response.headers.items()
                    if name.lower() == "retry-after"
                ),
                "",
            )
            try:
                seconds = float(retry_after)
            except ValueError:
                seconds = 0.0
            if math.isfinite(seconds) and seconds >= 0:
                delay = max(delay, seconds)
            if delay > self._max_retry_wait:
                raise error_type("Spotify API retry delay exceeds configured wait limit.")
            self._sleep(delay)
        raise AssertionError("Unreachable retry state.")  # pragma: no cover

    def _request_once(self, url: str) -> Response:
        request = Request(
            url,
            headers={
                "Authorization": f"Bearer {self._auth.get_access_token()}",
                "Accept": "application/json",
            },
        )
        try:
            return self._transport(request, self._timeout)
        except TransportError:
            raise SpotifyExtractionException("Spotify API could not be reached.") from None
