# ADR-0008: Use Fully Synthetic Data for Portfolio Analytics

## Status

Accepted for the portfolio demonstration scope. Live analytical use of Spotify-derived
content remains outside this decision until the exact permitted use is established and
documented.

## Context

The repository implements an offline-tested Spotify-compatible authentication and extraction
boundary and now contains complete offline contracts through the Glue/Silver, Snowflake, and
dbt layers. The portfolio use case demonstrates playlist churn, retention, position changes,
and artist presence.

OAuth authorization establishes technical access to an API resource. It does not, by itself,
establish permission for every downstream analytical, retention, or publication use. The
project therefore keeps portfolio analytics independent from any unresolved live-source usage
question.

## Decision

1. Use wholly invented playlists, artists, tracks, IDs, dates, and changes for portfolio
   analytics, warehouse demonstrations, screenshots, and sample reports. Relabeling or
   anonymizing captured Spotify responses is not treated as synthetic data.
2. Retain the API client and offline contract tests as compatibility engineering. Do not present
   offline tests as proof that live API access or downstream analytical use has been approved.
3. Treat live extraction as a separately governed integration path. Do not feed live
   Spotify-derived data into portfolio marts under the current decision.
4. Preserve the existing architecture, daily fact grain, source-version lineage, and physical
   execution IDs. This ADR changes the demonstration data boundary, not the warehouse model.
5. Keep the default validation path synthetic and reproducible. Cloud execution may still use
   AWS/Snowflake to prove engineering behavior, but the analytical records themselves remain
   synthetic unless a later decision establishes permitted real-source use.

## Alternatives Considered

- **Assume OAuth consent permits portfolio analytics:** rejected because access and downstream
  use are separate concerns.
- **Discard the Spotify-compatible ingestion work:** unnecessary; synthetic scenarios can still
  exercise pagination, consistency, retries, lineage, replay, Spark, Snowpipe contracts, dbt,
  and BI modeling.
- **Use another real dataset:** possible later if its license and access terms explicitly support
  the intended portfolio analytics.

## Consequences

Portfolio metrics and screenshots must be labeled synthetic and must not be presented as real
Spotify audience, market-share, or artist-performance findings. A meaningful longitudinal
synthetic demo corpus remains a separate deliverable from the current contract implementation.

If live integration is considered later, document the permitted use, retention/deletion rules,
display/attribution obligations, and any personal-data requirements before enabling that path.
Bronze immutability is an engineering replay rule, not an exemption from externally required
deletion.

## Review Conditions

Revisit this decision only when there is documented permission covering the exact analytical
use, a relevant change in source terms, or a replacement source with suitable rights.

## References

- [Spotify Developer Policy](https://developer.spotify.com/policy)
- [Spotify Developer Terms](https://developer.spotify.com/terms)
- [Spotify Web API playlist items reference](https://developer.spotify.com/documentation/web-api/reference/get-playlists-items)
