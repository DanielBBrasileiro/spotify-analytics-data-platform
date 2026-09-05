# Local Spotify ingestion

## Authentication (Issue #1)

`SpotifyAuthClient` implements ADR-0007 using Python's standard library; it has
no third-party runtime dependencies. Obtain user consent separately, then supply
`SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, and `SPOTIFY_REFRESH_TOKEN` through
the process environment or an injected mapping. The client does not load `.env`
files or perform the initial browser flow.

```python
from spotify_data_platform.auth import SpotifyAuthClient

auth = SpotifyAuthClient.from_env()
# Pass auth to the extractor; do not print or log access or refresh tokens.
```

Call `get_access_token()` immediately before dispatching a request. The client
exchanges the refresh token with HTTP Basic authentication, verifies TLS, rejects
redirects, and uses a 10-second socket timeout. It reuses tokens until 60 seconds
before expiry, measured from the start of the exchange with a monotonic clock.
For TTLs shorter than 120 seconds, the buffer is half the TTL. A lock prevents
concurrent callers from performing duplicate refreshes in the same instance.

`SpotifyAuthException` reports sanitized authentication failures. An
`InvalidGrantException` requires operator reauthorization; the client discards
the rejected token and does not retry it. Network and other HTTP failures are
reported immediately; authentication does not have an implicit retry loop.
Tokens and response bodies are excluded from client/response representations;
the library emits no credential-bearing logs.

If Spotify returns a rotated refresh token, subsequent exchanges use it.
`auth.refresh_token` deliberately exposes that secret to an explicit persistence
adapter. Rotation is **in-memory only** in M1; M2 must securely persist the current
token before the process exits. Never log this property or include it in artifacts.

The [Spotify refresh guide](https://developer.spotify.com/documentation/web-api/tutorials/refreshing-tokens)
documents optional token rotation and currently specifies a six-month refresh
token lifetime for dashboard-registered apps. Scheduled refreshes do not extend
that lifetime; operator reauthorization remains necessary.

## Playlist extraction (Issue #2)

```python
import os

from spotify_data_platform.auth import SpotifyAuthClient
from spotify_data_platform.extraction import PlaylistItemsExtractor

extractor = PlaylistItemsExtractor(SpotifyAuthClient.from_env())
snapshot = extractor.extract(os.environ["SPOTIFY_PLAYLIST_ID"])
```

This example makes live, authenticated Spotify requests when explicitly run with
operator-supplied credentials and an accessible 22-character playlist ID. It does
not write files or provision infrastructure. Initial consent remains a separate step.

The JSON-serializable result contains:

| Key | Content |
| --- | --- |
| `playlist_id` | Requested Spotify playlist ID |
| `spotify_snapshot_id` | Verified upstream playlist version |
| `playlist` | Initial, unmodified playlist metadata response |
| `pages` | Unmodified `/items` responses in request order |
| `items` | Consolidated items in source order, including nulls and duplicates |

Pagination uses `limit=50`, advances the offset by the actual item count, and
validates `next`, `total`, `offset`, and `limit`. The client constructs all URLs
against Spotify's fixed API origin instead of following upstream continuation
URLs. Contradictory pagination metadata or more than `max_pages` (default 1,000)
raises `PaginationException`. Item payloads, including the current API's `item`
field, are not normalized or filtered; technical transformation belongs to Glue.

The [items endpoint](https://developer.spotify.com/documentation/web-api/reference/get-playlists-items)
does not include `snapshot_id`. The extractor reads it from the
[playlist endpoint](https://developer.spotify.com/documentation/web-api/reference/get-playlist)
before pagination and after every page, including the final page. An observed
change raises `SnapshotChangedException`; callers must restart the entire read.
The method returns only a complete, verified result. This is an optimistic version
check, **not a server-side transaction or pinned historical read**. No partial
document is returned on failure. Each successful extraction costs one initial
metadata request plus two requests per items page, excluding authentication/retries.

HTTP 429 and 5xx responses receive up to **five retries after the initial attempt**
per request. Delays use exponential backoff (1, 2, 4, ... seconds, capped at 60)
plus up to one second of jitter, and never fall below a valid numeric `Retry-After`.
Malformed, negative, and non-finite header values fall back to backoff. A wait
above `max_retry_wait` (default 300 seconds) fails immediately instead of retrying
early. Throttling exhaustion raises `RateLimitExceededException`; other HTTP,
transport, and malformed-response failures raise `SpotifyExtractionException`.
HTTP 401/403 and transport failures are not retried automatically. The auth client
is consulted before every attempt, including after a rate-limit wait.

`timeout` is a per-socket-operation timeout, not a total extraction deadline.
The snapshot is assembled in memory; `pages` and `items` duplicate content when
serialized. Persistence, run IDs, business dates, and ingestion manifests remain
separate backlog work. M1 tests do not demonstrate live Spotify authorization.

## Offline verification

Install the `dev` extra and run `make check`. Ruff validates lint and formatting;
coverage runs pytest with branch measurement and requires at least 91% overall
coverage. Tests inject HTTP responses and clocks, block socket connections, and
use synthetic credentials only. An integration test exercises the real OAuth,
HTTP, and extraction components with a scripted urllib boundary, including token
rotation and expiry during a rate-limit wait. These tests establish local behavior, not live
Spotify access or cloud deployment readiness.
