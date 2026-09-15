# ADR-0009: Use CC0 Source Metadata with a Synthetic Temporal Demo

## Status

Accepted. This ADR supersedes ADR-0008 only for the current portfolio demonstration dataset.
ADR-0008's separation between technical API access and permission for downstream live-source
analytics remains unchanged.

## Context

The live Spotify-compatible extractor remains implemented and offline-tested, but the current
Spotify Development Mode access available to the project does not provide a live Web API path
for this deployment. The cloud validation still needs a small, reproducible Bronze input that
can exercise Glue, Snowpipe, Snowflake, dbt, retries, and longitudinal marts without purchasing
or depending on a third-party subscription.

The Kaggle dataset `jeremycte/spotify-10000-songs-dataset` is published as **CC0-1.0** and its
`data.csv` contains playlist, track, artist, add-time, title, album-name, and duration fields.
It does not contain a historical daily playlist series, album IDs, album release metadata, or
the explicit-content flag.

## Decision

1. Use a small local subset of the CC0 dataset as the current portfolio source corpus. Do not
   commit or redistribute the raw CSV in this repository; attribution and provenance remain
   documented even though CC0 does not require attribution.
2. Preserve source `playlist_id`, `track_id`, `artist_id`, names, durations, and `date_added`
   values where available.
3. Generate clearly namespaced deterministic album keys because the source has album names but
   no album IDs. Record that generated field in Bronze provenance.
4. Preserve unavailable attributes as unknown instead of fabricating them. In particular,
   `is_explicit` is nullable through Silver/Landing and album release/type/count remain null.
5. Generate three consecutive daily playlist states deterministically to exercise NEW,
   RETAINED, EXITED, rank movement, backfill, and idempotency. The daily membership,
   positions, snapshot IDs, playlist display label/owner, and generated album keys are demo
   adaptations and are not represented as observed Spotify history.
6. Keep downloaded source files and generated cloud-demo artifacts under `tmp/`, which is
   ignored by Git. Only source-adapter code, tests, contracts, and documentation are versioned.
7. Keep the live Spotify API/Lambda path as a separate optional integration. Do not claim live
   Web API validation until that integration is actually executed under permitted access.

## Consequences

- The public portfolio can demonstrate the complete downstream cloud engineering path without
  claiming that synthetic daily churn reflects real playlist behavior.
- Track/artist/playlist metadata has a reproducible public source, while temporal metrics remain
  controlled test scenarios.
- `explicit_pct` is null when a day's tracks have no known explicit flag; unknown values are not
  silently counted as non-explicit.
- Album IDs in the demo are source-adapter keys, not Spotify provider IDs.
- The existing Bronze shape, six Silver datasets, Snowflake Landing topology, dbt fact grain,
  and marts remain unchanged.

## References

- Kaggle dataset: https://www.kaggle.com/datasets/jeremycte/spotify-10000-songs-dataset
- Creative Commons CC0 1.0: https://creativecommons.org/publicdomain/zero/1.0/
