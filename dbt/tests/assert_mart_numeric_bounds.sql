select 'playlist_trends_explicit_pct' as violation, playlist_id, snapshot_date
from {{ ref('mart_playlist_trends') }}
where explicit_pct < 0 or explicit_pct > 100

union all

select 'playlist_trends_turnover_rate' as violation, playlist_id, snapshot_date
from {{ ref('mart_playlist_trends') }}
where turnover_rate < 0 or turnover_rate > 1

union all

select 'track_lifecycle_tenure' as violation, playlist_id, snapshot_date
from {{ ref('mart_track_lifecycle') }}
where cumulative_days_on_playlist < 1

union all

select 'artist_playlist_share' as violation, artist_id as playlist_id, snapshot_date
from {{ ref('mart_artist_presence') }}
where playlist_share < 0 or playlist_share > 1

union all

select 'playlist_trends_distinct_tracks' as violation, playlist_id, snapshot_date
from {{ ref('mart_playlist_trends') }}
where distinct_track_count < 0 or distinct_track_count > total_tracks
