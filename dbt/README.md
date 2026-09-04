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

## Planned Directory Structure

```
dbt/
├── dbt_project.yml
├── packages.yml
├── profiles.yml.example
├── macros/
│   └── generate_surrogate_key.sql
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
    └── assert_positive_track_durations.sql
```
