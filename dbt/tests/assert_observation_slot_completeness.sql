with slot_counts as (
    select
        playlist_id,
        snapshot_date,
        count(distinct track_position) as landed_slot_count
    from {{ ref('stg_spotify_playlist_snapshots') }}
    group by playlist_id, snapshot_date
)
select
    o.playlist_id,
    o.snapshot_date,
    o.valid_track_count,
    coalesce(s.landed_slot_count, 0) as landed_slot_count
from {{ ref('stg_spotify_playlist_observations') }} o
left join slot_counts s
  on o.playlist_id = s.playlist_id
 and o.snapshot_date = s.snapshot_date
where o.valid_track_count != coalesce(s.landed_slot_count, 0)
