select *
from {{ ref('stg_spotify_playlist_observations') }}
where source_item_count < 0
   or valid_track_count < 0
   or rejected_item_count < 0
   or source_item_count != valid_track_count + rejected_item_count
