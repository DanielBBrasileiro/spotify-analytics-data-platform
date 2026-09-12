select s.*
from {{ ref('stg_spotify_playlist_snapshots') }} s
left join {{ ref('stg_spotify_playlist_observations') }} o
  on s.playlist_id = o.playlist_id
 and s.snapshot_date = o.snapshot_date
 and s.pipeline_run_id = o.pipeline_run_id
 and s.spotify_snapshot_id = o.spotify_snapshot_id
where o.playlist_id is null
