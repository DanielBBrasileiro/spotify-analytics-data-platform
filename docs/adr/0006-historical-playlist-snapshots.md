# ADR-0006: Store Historical Playlist Snapshots Instead of Current-State Overwrite

## Status
Accepted

## Context
Standard tutorial pipelines for music APIs typically overwrite the current state of a playlist on each execution (e.g., updating a single `current_playlist_tracks` table). While simple, this approach loses all historical context and temporal dynamics:
- It cannot answer which tracks entered or exited a playlist between dates.
- It cannot determine the retention duration (tenure) of a track on a chart or editorial playlist.
- It cannot observe how playlist composition, genre distribution, or artist concentration evolve over time.
- It cannot correlate track popularity spikes with playlist placement dates.

To build an enterprise-caliber data platform, the architecture must support longitudinal analytics and temporal analysis.

## Decision
We decide to model playlist track membership as an **immutable, append-only historical snapshot series**:
1. **Raw Bronze Ingestion**: Every daily pipeline run lands an immutable JSON document representing the state of the monitored playlist at that point in time (`ingestion_date=YYYY-MM-DD/run_id=<id>/`).
2. **Silver Parquet Dataset**: Glue outputs a point-in-time snapshot entity dataset (`silver/playlist_snapshots/`) recording every track present, its positional index (`position`), and the ingestion timestamp.
3. **Snowflake Fact Table**: dbt models this into `fact_playlist_snapshot`, capturing track-playlist associations per snapshot.
4. **Marts Layer Analytics**: dbt models compute daily churn, additions, removals, and tenure via window functions (e.g., `LAG`, `LEAD`) across historical snapshots.

### Natural Key & Surrogate Key Evaluation
We evaluate the uniqueness criteria for historical snapshot records:
- **Candidate Natural Key**: `playlist_id` + `track_id` + `snapshot_date` (or `snapshot_timestamp`).
- **Edge Case Considered**: Can a track appear more than once in the same playlist at the same point in time? Yes, Spotify playlists allow duplicate track entries at different positional indices.
- **Adopted Natural Key**: `playlist_id` + `track_id` + `position` + `snapshot_timestamp`.
- **Surrogate Hash Key**: MD5 / SHA-256 hash of `playlist_id || '-' || track_id || '-' || position || '-' || snapshot_timestamp` generated in dbt using `dbt_utils.generate_surrogate_key`.

## Alternatives Considered
- **Type 2 Slowly Changing Dimension (SCD-2) on Tracks**:
  - *Pros*: Compact storage showing start_date and end_date of track membership.
  - *Cons*: High transformation complexity and merge costs for high-churn playlists; does not easily preserve daily ranking/positional snapshots without complex interval queries.
- **Current-State Overwrite (Truncate & Load)**:
  - *Pros*: Extremely low storage requirement.
  - *Cons*: Complete destruction of historical analytics; defeats the core value proposition of the portfolio platform.

## Consequences

### Positive Consequences
- **Rich Analytical Capabilities**: Powers downstream questions:
  - Which tracks entered/exited this week?
  - What is the average track lifespan on "Today's Top Hits"?
  - How did an artist's playlist reach fluctuate month-over-month?
- **Idempotency & Replayability**: Any past day's state can be inspected or recomputed without guesswork.
- **Deterministic Modeling**: Simplifies fact table ingestion to append-only partitioned inserts.

### Negative Consequences
- **Storage Growth**: Table size scales linearly with `num_monitored_playlists * avg_tracks_per_playlist * 365 days`. For typical portfolio scale (e.g., 5 playlists of 50-100 tracks = ~500 rows/day), this represents ~182,500 rows/year, which is negligible in Snowflake and S3 (< 50 MB compressed).
- **Query Scan Filtering**: Analytical queries must filter on `snapshot_date` or use pre-aggregated marts to avoid scanning all historical snapshots.

## Risks
- Duplication from accidental re-runs on the same calendar day. Mitigated by scoping snapshot deduplication to `playlist_id + track_id + position + snapshot_date` or enforcing partition overwrite at the daily grain in Silver/Landing.

## Review Conditions
Review if monitored playlists scale to tens of thousands of items, requiring transition from daily full snapshots to change-data-capture (CDC) event logs.
