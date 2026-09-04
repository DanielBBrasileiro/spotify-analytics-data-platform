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
1. **Initial Interactive Consent (One-Time Setup)**: A developer/operator runs an initial interactive setup utility executing the **OAuth 2.0 Authorization Code Flow** to authenticate the user and obtain an initial `access_token` and long-lived `refresh_token` with scopes:
   - `playlist-read-private`
   - `playlist-read-collaborative`
2. **Secure Token Storage**: The resulting `refresh_token`, along with `client_id` and `client_secret`, is securely persisted in **AWS Secrets Manager** (`spotify/api/credentials`) for cloud execution, or in a local non-committed `.env` file for local development.
3. **Automated Runtime Refresh**: During scheduled pipeline executions, the extractor (AWS Lambda or local script) retrieves the `refresh_token` from Secrets Manager, exchanges it with Spotify's token endpoint (`https://accounts.spotify.com/api/token`) using `grant_type=refresh_token`, and acquires a short-lived `access_token` (valid for 1 hour) to execute playlist `/items` requests non-interactively.

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
- **Full Playlist Access**: Successfully accesses user-owned, followed, and collaborative playlists under authorized scopes.
- **Non-Interactive Scheduling**: Lambda and Airflow execute on schedule using automated token refresh without requiring manual user intervention.
- **Least Privilege & Security**: The long-lived secret stored in Secrets Manager is the refresh token; the operational access token is transient, cached in memory, and expires automatically.

### Negative Consequences
- **One-Time Bootstrap Step**: Requires an initial interactive authorization step to generate the initial refresh token prior to automated execution.
- **Token Invalidation Risk**: If the user revokes application access in their Spotify account, the refresh token becomes invalid and requires manual re-authorization.

## Risks
- Refresh token revocation or expiration if unused for extended periods. Mitigated by error detection in Lambda emitting a dedicated alert when token refresh fails with `invalid_grant`.

## Review Conditions
Review if Spotify introduces API key or service-account capabilities for backend data access that eliminate user-consent requirements.
