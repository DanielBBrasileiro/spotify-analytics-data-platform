with observed_playlists as (
    select
        snapshot_date,
        count(distinct playlist_id) as observed_playlist_count
    from {{ ref('stg_spotify_playlist_observations') }}
    group by snapshot_date
), artist_daily as (
    select
        a.artist_id,
        a.artist_name,
        f.snapshot_date,
        count(*) as total_tracks,
        count(distinct f.playlist_pk) as distinct_playlists,
        count_if(b.artist_order = 0) as primary_artist_tracks,
        count_if(b.artist_order > 0) as featured_artist_tracks,
        min(f.track_position) as best_observed_position
    from {{ ref('fact_playlist_snapshot') }} f
    inner join {{ ref('bridge_track_artist') }} b
        on f.track_pk = b.track_pk
    inner join {{ ref('dim_artist') }} a
        on b.artist_pk = a.artist_pk
    group by a.artist_id, a.artist_name, f.snapshot_date
)

select
    a.*,
    1.0 * a.distinct_playlists / nullif(o.observed_playlist_count, 0) as playlist_share
from artist_daily a
inner join observed_playlists o
    on a.snapshot_date = o.snapshot_date
