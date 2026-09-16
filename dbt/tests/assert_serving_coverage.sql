-- A descriptive join must never silently drop analytical rows.
select 'playlist_daily' as dataset
where (select count(*) from {{ ref('bi_playlist_daily') }})
   != (select count(*) from {{ ref('mart_playlist_trends') }})
union all
select 'track_daily'
where (select count(*) from {{ ref('bi_track_daily') }})
   != (select count(*) from {{ ref('mart_track_lifecycle') }})
union all
select 'track_changes'
where (select count(*) from {{ ref('bi_track_changes') }})
   != (select count(*) from {{ ref('mart_playlist_changes') }})
union all
select 'artist_daily'
where (select count(*) from {{ ref('bi_artist_daily') }})
   != (select count(*) from {{ ref('mart_artist_presence') }})
