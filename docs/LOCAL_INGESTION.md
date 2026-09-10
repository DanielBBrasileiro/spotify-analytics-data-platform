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
serialized. M1 tests do not demonstrate live Spotify authorization.

## Run metadata and local Bronze persistence (Issue #4)

`PipelineRunMetadata` is the validated execution-lineage contract used to keep
physical execution identity separate from the logical business observation date.
It requires a UUID v4 `pipeline_run_id`, the verified Spotify source version,
playlist ID, `snapshot_date`, timezone-aware capture timestamp, extracted record
count, and lifecycle status. Capture timestamps are normalized to UTC.

```python
from datetime import UTC, date, datetime
from uuid import uuid4

from spotify_data_platform.ingestion import (
    LocalBronzeWriter,
    PipelineRunMetadata,
    RunStatus,
)

run = PipelineRunMetadata(
    pipeline_run_id=uuid4(),
    spotify_snapshot_id=snapshot["spotify_snapshot_id"],
    playlist_id=snapshot["playlist_id"],
    snapshot_date=date.today(),
    snapshot_timestamp=datetime.now(UTC),
    records_extracted=len(snapshot["items"]),
    status=RunStatus.SUCCESS,
)

path = LocalBronzeWriter().write(snapshot, run)
```

The default writer mirrors the future S3 Bronze key hierarchy under the gitignored
`data/` directory:

```text
data/bronze/spotify/playlist_tracks/
  ingestion_date=YYYY-MM-DD/
    run_id=<pipeline_run_id>/
      playlist_<playlist_id>.json
```

`snapshot_date` is the canonical business observation date. `ingestion_date` is
instead derived from the actual **UTC capture timestamp**, so a retry or historical
backfill can target an earlier business date without falsifying its physical landing
date. A new execution receives a new UUID v4 and therefore a new run directory.

Local Bronze files preserve the extraction envelope as JSON without injecting
telemetry into the source payload. The writer checks playlist/source-version lineage
and the raw item count before publishing. Only complete `SUCCESS` observations are
landed. Publication is no-clobber and atomic at the final-path boundary: an existing
object is never overwritten and temporary files are removed on failure. This mirrors
ADR-0002's append-only rule while keeping AWS S3 calls out of M1.

The metadata model supports the broader observability lifecycle states (`RUNNING`,
`SUCCESS`, `FAILED`, `PARTIAL`), but persisted failure/run manifests are intentionally
separate from Bronze raw objects and remain later observability work.

## Offline verification

Issue #3 adds a [synthetic fixture corpus](../tests/fixtures/spotify/README.md)
with a 50+2-item traversal, a single-page mixed-media scenario, and a 429 body.
Integration tests feed these files through the real extractor with injected HTTP
responses and sleep functions, without contacting Spotify or waiting on retries.

`spotify_data_platform.extraction.items.parse_playlist_item(entry)` provides an
opt-in inspection result: `kind`, `is_local`, and ordered `artist_ids`. It
distinguishes tracks, episodes, unavailable items, and unsupported future media.
Null and duplicate artist IDs retain their slots. Missing keys or malformed
containers raise `SpotifyItemParseException` with no raw values in the message.
Unknown fields are ignored, and the original entry is never mutated. The raw
extractor does not call this parser or drop records; full schema enforcement and
Silver normalization remain M3 responsibilities.

CI gives the complete pytest command, including coverage startup, a five-second
wall-clock budget using the Ubuntu runner's `timeout` command. Timeout exits fail
the job. Checkout, dependency installation, linting, and reporting are outside
this test budget; the total GitHub Actions job is not expected to finish in five
seconds. `--durations=5` reports the slowest tests for diagnosis. Local
`make check` keeps the same offline suite and coverage gate without imposing a
machine-dependent deadline.

Install the `dev` extra and run `make check`. Ruff validates lint and formatting;
coverage runs pytest with branch measurement and requires at least 91% overall
coverage. Tests inject HTTP responses and clocks, block socket connections, and
use synthetic credentials only. An integration test exercises the real OAuth,
HTTP, and extraction components with a scripted urllib boundary, including token
rotation and expiry during a rate-limit wait. A second integration path extracts a
checked-in Spotify fixture and lands it through the real local Bronze writer, proving
the path and raw JSON round trip without network access. These tests establish local
behavior, not live Spotify access or cloud deployment readiness.
