with denominators as (
    select snapshot_date, count(distinct playlist_id) as observed_playlists
    from {{ ref('stg_spotify_playlist_observations') }}
    group by snapshot_date
), expected as (
    select
        a.artist_id,
        f.snapshot_date,
        count(distinct f.playlist_pk) / nullif(d.observed_playlists, 0) as expected_share
    from {{ ref('fact_playlist_snapshot') }} f
    inner join {{ ref('bridge_track_artist') }} b on f.track_pk = b.track_pk
    inner join {{ ref('dim_artist') }} a on b.artist_pk = a.artist_pk
    inner join denominators d on f.snapshot_date = d.snapshot_date
    group by a.artist_id, f.snapshot_date, d.observed_playlists
)
select m.artist_id, m.snapshot_date, m.playlist_share, e.expected_share
from {{ ref('mart_artist_presence') }} m
inner join expected e
  on m.artist_id = e.artist_id
 and m.snapshot_date = e.snapshot_date
where abs(m.playlist_share - e.expected_share) > 0.000001
