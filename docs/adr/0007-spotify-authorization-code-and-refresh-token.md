# ADR-0007: Use Authorization Code with Refresh Tokens and Periodic Reauthorization

## Status

Accepted; lifecycle and access wording revised 2026-09-07 and rechecked 2026-09-09.

## Context

The Spotify integration needs a user-scoped token. The current playlist items
endpoint accepts playlists owned by the authorized user or playlists on which
that user is a collaborator. Following a playlist alone is insufficient. Client
Credentials does not supply this user identity. Technical access must also respect
the source-use boundary in [ADR-0008](0008-synthetic-analytics-and-source-use-boundary.md).

## Decision

1. **Interactive authorization and reauthorization:** use Authorization Code for
   this confidential client. Initial consent occurs outside the implemented client.
   Dashboard-app refresh tokens have a six-month lifetime measured from user
   authorization. Exchanging access tokens does not extend it. Obtain new consent
   after expiration or revocation; do not describe consent as permanently one-off.
2. **Access-token exchange:** use `POST https://accounts.spotify.com/api/token`
   with HTTP Basic client authentication and `grant_type=refresh_token`.
   `expires_in` describes the access token, normally one hour. The implemented
   client uses the returned TTL and a monotonic expiry buffer.
3. **Failure handling:** `invalid_grant` raises `InvalidGrantException`, clears
   the rejected refresh token and cached access token, and blocks further exchanges from
   that client instance. Operator reauthorization is required; retrying that
   refresh token cannot repair the grant.
4. **Storage and rotation:** local callers inject credentials or process
   environment values. The client does not load `.env` files. Rotated refresh
   tokens are retained in memory only. Secure durable persistence belongs to M2's
   Secrets Manager adapter and must be designed before unattended cloud use.
5. **Access scopes:** retain the documented `playlist-read-private` and
   `playlist-read-collaborative` intent; verify the exact scopes for each endpoint
   when implementing consent. Scopes do not override ownership/collaboration checks.

## Implementation Boundary

`SpotifyAuthClient` and offline tests are implemented (Issue #1 / PR #38).
Initial browser consent tooling, authorization-date tracking, expiry reminders,
Secrets Manager writes, and Lambda/Airflow recovery alerts are planned. Neither
live authentication nor cloud token persistence has been validated by this suite.

## Alternatives Considered

- **Client Credentials:** useful for supported application-level endpoints, but
  insufficient for this user-scoped playlist contract.
- **Authorization Code with PKCE:** appropriate for public clients that cannot
  protect a secret; reconsider if a browser/mobile client is introduced.
- **Static bearer token:** short lifetime prevents durable scheduled operation.

## Consequences

Scheduled exchanges can run without user interaction while the grant is valid.
Periodic operator participation is part of the intended operating model. Future
automation must record authorization timing explicitly; neither access-token TTL
nor refresh-token rotation proves a renewed six-month grant.

## Review Conditions

Review when Spotify changes token lifetime, playlist access, authorization flows,
or permitted source use, and before implementing consent or durable token storage.

## References

Rechecked 2026-09-09:
- [Authorization Code](https://developer.spotify.com/documentation/web-api/tutorials/code-flow)
- [Refresh token lifecycle and invalid_grant](https://developer.spotify.com/documentation/web-api/tutorials/refreshing-tokens)
- [Playlist items access](https://developer.spotify.com/documentation/web-api/reference/get-playlists-items)
