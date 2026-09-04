# dbt Core Analytics Engineering

This directory contains the dbt Core project running transformations natively on Snowflake.

---

## Architectural Responsibility

Per **ADR-0005**, dbt Core is responsible for in-warehouse analytical transformations, dimensional modeling, business metrics, and data testing inside Snowflake.

### Core Responsibilities:
1. **Staging Layer (`models/staging/`)**:
   - Clean column naming conventions (`stg_spotify_tracks`, `stg_spotify_artists`, `stg_spotify_albums`, `stg_spotify_playlist_snapshots`).
   - Light casting, renaming, and deduplication assertions on raw Landing tables.
2. **Core Dimensional Layer (`models/core/`)**:
   - Kimball-style dimensional models:
     - `dim_track` (track attributes, surrogate keys)
     - `dim_artist` (artist attributes)
     - `dim_album` (album metadata)
     - `dim_playlist` (playlist metadata)
     - `bridge_track_artist` (many-to-many bridge relationship)
     - `fact_playlist_snapshot` (historical track membership, position, addition timestamp)
3. **Marts Layer (`models/marts/`)**:
   - Aggregated analytical models tailored for business reporting:
     - `mart_artist_performance` (presence across playlists, total reach)
     - `mart_playlist_trends` (genre composition, average audio profile trends)
     - `mart_track_popularity` (popularity trajectory over time)
     - `mart_playlist_changes` (daily track entries, exits, and retention duration)
4. **Data Quality Tests (`tests/`)**:
   - Generic schema tests (unique, not_null, accepted_values, relationships).
   - Singular SQL tests for domain rules (e.g., track durations > 0, validity ranges for popularity 0-100).

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
│       ├── mart_artist_performance.sql
│       ├── mart_playlist_trends.sql
│       ├── mart_track_popularity.sql
│       └── mart_playlist_changes.sql
└── tests/
    └── assert_positive_track_durations.sql
```
