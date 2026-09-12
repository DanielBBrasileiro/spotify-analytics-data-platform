# ADR-0007: Use Spotify Authorization Code Flow with Stored Refresh Token for Automated Ingestion

## Status
Accepted

## Context
Initial pipeline designs assumed the Spotify Web API could be accessed using the OAuth 2.0 **Client Credentials Flow**. While Client Credentials provides simple application-level authentication without user interaction, it carries critical architectural limitations under Spotify's modern API access model:
1. **Scope and Endpoint Restrictions**: Client Credentials tokens cannot access private playlists, collaborative playlists, or user-curated libraries. Under Spotify's 2026 Development Mode guidelines, applications are restricted to resources explicitly accessible by authorized application users with appropriate scopes (`playlist-read-private`, `playlist-read-collaborative`).
2. **Access Boundary**: The Client Credentials flow does not associate requests with an authorized user identity, causing playlist inspection endpoints to reject requests or return truncated/empty results for user-governed playlists.
3. **Automated Scheduled Execution**: Production pipelines (orchestrated by Airflow and executed by AWS Lambda) require automated, non-interactive execution without human intervention at scheduled run times.

## Decision
We decide to adopt a **two-phase authentication architecture**:
1. **Interactive Consent and Reauthorization**: A developer/operator completes the **OAuth 2.0 Authorization Code Flow** externally to obtain an initial `access_token` and `refresh_token`, repeating authorization when the source requires it, with scopes:
   - `playlist-read-private`
   - `playlist-read-collaborative`
2. **Secure Token Storage**: The resulting `refresh_token`, along with `client_id` and `client_secret`, is securely persisted in **AWS Secrets Manager** (`spotify/api/credentials`) for cloud execution, or in a local non-committed `.env` file for local development.
3. **Automated Runtime Refresh**: Between required operator reauthorizations, scheduled executions retrieve the `refresh_token` from Secrets Manager, exchange it with Spotify's token endpoint (`https://accounts.spotify.com/api/token`) using `grant_type=refresh_token`, and use the returned short-lived `access_token` for playlist `/items` requests. Runtime code follows the returned token lifetime rather than assuming a permanent credential.

## Alternatives Considered
- **Client Credentials Flow**:
  - *Pros*: Completely headless; requires no initial browser-based user consent.
  - *Cons*: Cannot read private or collaborative playlists; violates 2026 Spotify Development Mode access constraints.
- **Authorization Code Flow with Proof Key for Code Exchange (PKCE)**:
  - *Pros*: Mitigates authorization code interception attacks for public clients (e.g., mobile apps or Single Page Applications) that cannot securely store a `client_secret`.
  - *Cons*: Our extraction runtime (AWS Lambda / Airflow backend) is a confidential server-side client with a dedicated secret store (AWS Secrets Manager). Standard Authorization Code flow with confidential client secret authentication is fully secure and standard for server-to-server daemon integration.
- **Manual Static Bearer Token Injection**:
  - *Pros*: Minimal setup code.
  - *Cons*: Spotify access tokens expire after 3600 seconds (1 hour). Static tokens break automated daily scheduling and fail production reliability standards.

## Consequences

### Positive Consequences
- **Scoped Playlist Access**: Uses authorized user scopes rather than claiming unrestricted playlist access.
- **Non-Interactive Scheduled Refresh**: Scheduled runs can refresh access tokens without manual intervention between required operator reauthorizations.
- **Least Privilege & Security**: The long-lived secret stored in Secrets Manager is the refresh token; the operational access token is transient, cached in memory, and expires automatically.

### Negative Consequences
- **Operator Authorization Boundary**: Requires interactive authorization initially and again whenever the refresh-token lifecycle or revocation state requires it.
- **Token Invalidation Risk**: If the user revokes application access in their Spotify account, the refresh token becomes invalid and requires manual re-authorization.

## Risks
- Refresh-token revocation or expiration requires operator reauthorization. The implemented runtime clears cached credential/auth state on `invalid_grant`; dedicated operator alerting remains later orchestration/observability work.

## Review Conditions
Review if Spotify introduces API key or service-account capabilities for backend data access that eliminate user-consent requirements.
