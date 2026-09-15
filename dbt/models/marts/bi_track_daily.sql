{{ config(materialized='view', tags=['serving']) }}

select
    m.playlist_id,
    p.playlist_name,
    m.track_id,
    t.track_name,
    a.album_name,
    m.snapshot_date,
    m.cumulative_days_on_playlist,
    m.current_position + 1 as current_position,
    m.best_position + 1 as best_position,
    m.position_delta,
    p.source_type,
    p.temporal_state
from {{ ref('mart_track_lifecycle') }} m
inner join {{ ref('bi_playlist_daily') }} p
    on m.playlist_id = p.playlist_id and m.snapshot_date = p.snapshot_date
inner join {{ ref('dim_track') }} t on m.track_id = t.track_id
left join {{ ref('dim_album') }} a on t.album_pk = a.album_pk
