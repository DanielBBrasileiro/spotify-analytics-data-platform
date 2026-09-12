select o.playlist_id, o.snapshot_date
from {{ ref('stg_spotify_playlist_observations') }} o
left join {{ ref('mart_playlist_trends') }} t
  on o.playlist_id = t.playlist_id
 and o.snapshot_date = t.snapshot_date
where t.playlist_id is null
