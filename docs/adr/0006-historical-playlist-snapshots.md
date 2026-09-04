# ADR-0006: Store Historical Playlist Snapshots with Source-Version Lineage

## Status
Accepted (Revised for 2026 API & Canonical Grain Alignment)

## Context
Standard music API tutorial pipelines overwrite current playlist state on each run (e.g., maintaining a single `current_playlist_tracks` table). This destroys temporal dynamics:
- Which tracks entered or exited a playlist between dates.
- Retention duration (days on playlist).
- Playlist rank movements, volatility, and artist representation shifts over time.

To build an enterprise data platform, we must preserve historical snapshot states. However, the snapshot model must define a mathematically sound canonical grain that guarantees idempotency across pipeline retries and arbitrary historical backfills.

## Decision
We decide to model playlist track membership as an **immutable, append-only historical snapshot series** anchored by a deterministic daily canonical grain and upstream source-version lineage:

1. **Source Version Lineage (`spotify_snapshot_id`)**: Every Spotify playlist response includes a `snapshot_id` representing the upstream version identifier. We capture this as first-class metadata to track when Spotify playlist contents actually mutated versus when our pipeline merely observed an unchanged state.
2. **Physical Run vs. Business Date Identity**:
   - `pipeline_run_id`: A UUID v4 generated per execution. It is intentionally non-deterministic and represents physical execution lineage.
   - `snapshot_date`: The canonical business observation date (UTC).
   - `snapshot_timestamp`: The specific timestamp when the observation occurred.
3. **Canonical Fact Grain**:
   For our daily snapshot cadence, the canonical natural grain of `fact_playlist_snapshot` is:
   `playlist_id` + `snapshot_date` + `track_position`
   *(One canonical playlist slot per playlist per business date).*
   The `track_id` represents the observed track entity situated at that slot.
4. **Surrogate Key (`snapshot_pk`)**:
   Computed as the deterministic MD5 / SHA-256 hash of:
   `playlist_id || '-' || snapshot_date || '-' || track_position`
   *(Generated in dbt via `dbt_utils.generate_surrogate_key`).*
5. **Idempotent Merge Semantics**:
   Pipeline retries or backfills targeting an existing `snapshot_date` execute a deterministic SQL `MERGE` on `snapshot_pk`. Retrying a failed execution updates/matches existing records rather than producing duplicate rows.

### Why Execution Timestamps Were Excluded from the Natural Key
Earlier drafts evaluated `playlist_id + track_id + position + snapshot_timestamp`. Including an ever-changing execution timestamp in the natural key breaks idempotency: if a pipeline run is re-executed or retried on the same date, a new timestamp would yield distinct surrogate keys, causing duplicate snapshot records for the same logical business date. Pinned to `snapshot_date`, the grain remains strictly deterministic.

### Multi-Snapshot Future Evolution
If the platform evolves from a daily snapshot cadence to intra-day snapshots (e.g., hourly or event-triggered), the canonical grain must be revised to include the upstream `spotify_snapshot_id` or an explicit snapshot sequence identifier (`playlist_id + spotify_snapshot_id + track_position`).

## Alternatives Considered
- **Type 2 Slowly Changing Dimension (SCD-2) on Track Placement**:
  - *Pros*: Compact storage showing effective date ranges (`valid_from`, `valid_to`).
  - *Cons*: High merge complexity and compute overhead when playlists undergo frequent track reordering; difficult to compute daily ranking matrices without complex interval expansion queries.
- **Current-State Overwrite (Truncate & Load)**:
  - *Pros*: Minimal storage.
  - *Cons*: Destroys all temporal analysis; eliminates track tenure and churn metrics.

## Consequences

### Positive Consequences
- **Strict Idempotency**: Backfills and retries are mathematically deterministic and safe against accidental row duplication.
- **Upstream Change Detection**: `spotify_snapshot_id` enables downstream models to identify whether playlist contents changed between consecutive pipeline runs.
- **Rich Temporal Analytics**: Powers queries for daily entry/exit churn, track longevity, and positional volatility.

### Negative Consequences
- **Storage Growth**: Table scales with `num_monitored_playlists * avg_tracks * 365 days` (~182,500 rows/year for 10 playlists of 50 tracks), which remains negligible in Snowflake and S3 (< 50 MB compressed).
- **Date Filtering Required**: Queries must filter on `snapshot_date` or consume pre-aggregated marts to avoid scanning entire history.

## Risks
- Upstream playlist modified midway through extraction pagination. Mitigated by comparing `spotify_snapshot_id` across paginated chunks and aborting if the snapshot ID shifts during pagination.

## Review Conditions
Review if monitored playlists scale to tens of thousands of items or intra-day cadences, requiring change-data-capture (CDC) event logs.
