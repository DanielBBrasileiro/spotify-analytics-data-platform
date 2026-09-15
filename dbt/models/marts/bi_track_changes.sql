{{ config(materialized='view', tags=['serving']) }}

select
    m.playlist_id,
    p.playlist_name,
    m.track_id,
    t.track_name,
    m.snapshot_date,
    m.movement_status,
    m.current_position + 1 as current_position,
    m.previous_position + 1 as previous_position,
    m.position_delta,
    m.consecutive_days_retained,
    p.source_type,
    p.temporal_state
from {{ ref('mart_playlist_changes') }} m
inner join {{ ref('bi_playlist_daily') }} p
    on m.playlist_id = p.playlist_id and m.snapshot_date = p.snapshot_date
inner join {{ ref('dim_track') }} t on m.track_id = t.track_id
