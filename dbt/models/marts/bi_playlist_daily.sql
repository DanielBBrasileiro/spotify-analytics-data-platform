{{ config(materialized='view', tags=['serving']) }}

select
    m.playlist_id,
    p.playlist_name,
    m.snapshot_date,
    m.total_tracks as track_slots,
    m.distinct_track_count,
    m.avg_duration_ms / 1000.0 as avg_duration_seconds,
    m.explicit_pct / 100.0 as explicit_share,
    m.avg_release_age_years,
    m.new_tracks,
    m.exited_tracks,
    m.turnover_rate,
    case when startswith(o.spotify_snapshot_id, 'cc0-sim-')
        then 'cc0_demo' else 'unclassified' end as source_type,
    case when startswith(o.spotify_snapshot_id, 'cc0-sim-')
        then 'synthetic' else 'unclassified' end as temporal_state,
    o.snapshot_timestamp
from {{ ref('mart_playlist_trends') }} m
inner join {{ ref('dim_playlist') }} p on m.playlist_id = p.playlist_id
inner join {{ ref('stg_spotify_playlist_observations') }} o
    on m.playlist_id = o.playlist_id and m.snapshot_date = o.snapshot_date
