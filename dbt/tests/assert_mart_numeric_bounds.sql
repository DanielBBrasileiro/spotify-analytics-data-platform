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

