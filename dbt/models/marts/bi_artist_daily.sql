{{ config(materialized='view', tags=['serving']) }}

with provenance as (
    select
        snapshot_date,
        case when count_if(temporal_state != 'synthetic') = 0
            then 'synthetic' else 'mixed_or_unclassified' end as temporal_state,
        case when count_if(source_type != 'cc0_demo') = 0
            then 'cc0_demo' else 'mixed_or_unclassified' end as source_type
    from {{ ref('bi_playlist_daily') }}
    group by snapshot_date
)

select
    m.artist_id,
    m.artist_name,
    m.snapshot_date,
    m.total_tracks as credited_track_slots,
    m.distinct_playlists,
    m.primary_artist_tracks as primary_artist_slots,
    m.featured_artist_tracks as featured_artist_slots,
    m.best_observed_position + 1 as best_observed_position,
    m.playlist_share,
    p.source_type,
    p.temporal_state
from {{ ref('mart_artist_presence') }} m
inner join provenance p on m.snapshot_date = p.snapshot_date
