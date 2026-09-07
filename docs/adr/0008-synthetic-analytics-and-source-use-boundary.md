# ADR-0008: Use Fully Synthetic Data for Portfolio Analytics

## Status

Accepted for the portfolio demonstration scope (2026-09-07).
Live analytical use of Spotify data remains unresolved and is outside that scope.

## Context

The repository implements a Spotify-compatible authentication and extraction
boundary, validated with synthetic responses. The planned warehouse demonstrates
playlist churn, retention, position changes, and artist presence.

Spotify Developer Policy III.13 restricts analysis of Spotify Content and the
service. Developer Terms II.8 includes metadata and playlists in Spotify Content.
Our assessment is that the proposed live analytical use may conflict with this
restriction. OAuth consent establishes technical access; it does not establish
permission for every downstream use. We have no documented exception for this
project. This is a project scoping decision, not a claim of vendor approval.

## Decision

1. Use wholly invented playlists, artists, tracks, IDs, dates, and changes for
   portfolio analytics, warehouse demonstrations, screenshots, and sample reports.
   Relabeling or anonymizing captured Spotify responses is not synthetic data.
2. Retain the existing API client and offline contract tests. Describe them as
   offline-validated compatibility work, without claiming live access was tested.
3. Keep live extraction examples as conditional integration references, outside
   the default demonstration path. Do not feed live Spotify data to analytical
   marts or publish it as portfolio data under the current decision.
4. Preserve the planned engines, daily fact grain, source-version lineage, and
   physical execution IDs. This ADR changes the demonstration's data source scope,
   not the warehouse model or implementation boundaries.
5. Continue M1 metadata/persistence development against synthetic fixtures.
   A runnable synthetic end-to-end pipeline and cloud deployment remain future
   work; this documentation change does not implement a source switch or runner.

## Alternatives Considered

- **Assume user consent permits analytics:** rejected because API access and
  permitted use are separate questions.
- **Discard the engineering work:** unnecessary; synthetic scenarios can exercise
  pagination, consistency, retries, lineage, replay, Spark, and dimensional SQL.
- **Use another real dataset:** possible future decision after checking its license
  and access contract; no replacement provider is selected here.

## Consequences

Demonstrations must be labeled synthetic. Metrics describe simulated behavior and
must not be presented as real Spotify audience, market-share, or artist findings.
Existing fixtures cover contracts; a meaningful longitudinal demo corpus is still
to be implemented. The absence of paid infrastructure or live API validation must
remain visible in README and component documentation.

If live integration is considered later, establish the permitted use first and
document access, retention/deletion, and display/attribution requirements. Bronze
immutability is a normal-processing rule, not an exemption from required deletion
of personal data when consent is withdrawn.

## Review Conditions

Revisit with documented permission covering the exact analytical use, a relevant
change in official terms, or a separately approved source with suitable rights.
The owner reviews any resulting architecture/source change before implementation.

## References

Checked 2026-09-07:
- [Spotify Developer Policy, III.13 and I.1](https://developer.spotify.com/policy)
- [Spotify Developer Terms, II.8](https://developer.spotify.com/terms)
- [Playlist items access contract](https://developer.spotify.com/documentation/web-api/reference/get-playlists-items)
