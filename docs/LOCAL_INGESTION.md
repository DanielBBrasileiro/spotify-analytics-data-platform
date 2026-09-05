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

## Offline verification

Install the `dev` extra and run `make check`. Ruff validates lint and formatting;
coverage runs pytest with branch measurement and requires at least 91% overall
coverage. Tests inject HTTP responses and clocks, block socket connections, and
use synthetic credentials only. These tests establish local behavior, not live
Spotify access or cloud deployment readiness.
