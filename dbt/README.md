# dbt Core Analytics Engineering

This directory contains the dbt Core project running transformations natively on Snowflake.

---

## Architectural Responsibility

Per **ADR-0005**, dbt Core is responsible for in-warehouse analytical transformations, dimensional modeling, business metrics, and data testing inside Snowflake.

### Core Responsibilities:
1. **Staging Layer (`models/staging/`)**:
   - Clean column naming conventions (`stg_spotify_tracks`, `stg_spotify_artists`, `stg_spotify_albums`, `stg_spotify_track_artists`, `stg_spotify_playlist_snapshots`).
   - Light casting, renaming, item validation, and deduplication assertions on raw Landing tables.
2. **Core Dimensional Layer (`models/core/`)**:
   - Kimball-style dimensional models:
     - `dim_track` (track attributes, surrogate key `track_pk`)
     - `dim_artist` (artist attributes, surrogate key `artist_pk`)
     - `dim_album` (album metadata, surrogate key `album_pk`)
     - `dim_playlist` (playlist metadata, surrogate key `playlist_pk`)
     - `bridge_track_artist` (many-to-many bridge relationship, surrogate key `bridge_pk`)
     - `fact_playlist_snapshot` (incremental model merged on canonical surrogate key `snapshot_pk`)
3. **Marts Layer (`models/marts/`)**:
   - Aggregated analytical models tailored for business reporting:
     - `mart_artist_presence` (representation and presence across monitored playlists)
     - `mart_playlist_trends` (track count, explicit share, duration distribution, turnover)
     - `mart_track_lifecycle` (longevity, current rank, best position, position changes)
     - `mart_playlist_changes` (daily track entries, exits, and continuous days retained)
4. **Data Quality Tests (`tests/`)**:
   - Generic schema tests (unique, not_null, accepted_values, relationships).
   - Singular SQL tests for domain rules (e.g., positive track durations).

---

## Incremental Merge & Backfill Strategy

Per **ADR-0006**, `fact_playlist_snapshot` uses:
- `materialized = 'incremental'`
- `incremental_strategy = 'merge'`
- `unique_key = 'snapshot_pk'` (computed from `playlist_id + snapshot_date + track_position`)

Normal runs merge the target `snapshot_date`. Backfills accept explicit date ranges (`start_date` / `end_date`), enabling idempotent historical reprocessing.

---

## Project Structure

```
dbt/
├── dbt_project.yml
├── packages.yml
├── package-lock.yml
├── profiles.yml.example
├── requirements-dev.txt
├── macros/
│   ├── generate_schema_name.sql
│   └── snapshot_window.sql
├── models/
│   ├── staging/
│   │   ├── _staging_models.yml
│   │   ├── stg_spotify_artists.sql
│   │   ├── stg_spotify_albums.sql
│   │   ├── stg_spotify_tracks.sql
│   │   ├── stg_spotify_track_artists.sql
│   │   └── stg_spotify_playlist_snapshots.sql
│   ├── core/
│   │   ├── _core_models.yml
│   │   ├── dim_track.sql
│   │   ├── dim_artist.sql
│   │   ├── dim_album.sql
│   │   ├── dim_playlist.sql
│   │   ├── bridge_track_artist.sql
│   │   └── fact_playlist_snapshot.sql
│   └── marts/
│       ├── _marts_models.yml
│       ├── mart_artist_presence.sql
│       ├── mart_playlist_trends.sql
│       ├── mart_track_lifecycle.sql
│       └── mart_playlist_changes.sql
└── tests/
    ├── assert_positive_track_durations.sql
    ├── assert_nonnegative_positions.sql
    ├── assert_fact_snapshot_grain.sql
    ├── assert_bridge_artist_order.sql
    ├── assert_playlist_change_continuity.sql
    ├── assert_mart_numeric_bounds.sql
    └── assert_retention_streaks_positive.sql
```

## Offline development contract

M5 uses `dbt-core==1.12.4`, `dbt-snowflake==1.12.0`, and `dbt_utils==1.4.1`.
`profiles.yml.example` contains environment-variable placeholders only and hard-codes the
least-privileged `SPOTIFY_TRANSFORMER` role. CI uses the inert profile under
`tests/dbt_profile/` and runs `dbt parse --no-partial-parse`, which validates project
configuration, Jinja, refs/sources, macros, and the DAG without connecting to Snowflake.

Live `dbt build` remains a later cloud-validation gate; this repository does not claim
warehouse execution merely because the offline parse succeeds.

The incremental fact requires an explicit execution window at runtime: use
`--vars '{"snapshot_date": "YYYY-MM-DD"}'` for a daily merge or both `start_date` and
`end_date` for an idempotent backfill. It never uses a `max(snapshot_date)` watermark, so
older partitions remain re-runnable.

Staging chooses one coherent winning physical `pipeline_run_id` for each playlist/date
before exposing its slots. The fact then runs its normal `MERGE` and a scoped post-merge
cleanup removes obsolete positions that existed in an older retry but are absent from the
winning run. The cleanup only acts on playlist/date observations actually present in the
requested source window, so unrelated historical dates are untouched.

Track-level marts collapse repeated legitimate playlist slots for the same track/date to
the best (lowest numeric) observed position. The underlying fact keeps every slot at its
canonical `playlist_id + snapshot_date + track_position` grain.
