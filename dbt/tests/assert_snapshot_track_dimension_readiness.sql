select distinct s.playlist_id, s.snapshot_date, s.track_id
from {{ ref('stg_spotify_playlist_snapshots') }} s
left join {{ ref('stg_spotify_tracks') }} t
  on s.track_id = t.track_id
where t.track_id is null
