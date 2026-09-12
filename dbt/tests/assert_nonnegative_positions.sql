select *
from {{ ref('fact_playlist_snapshot') }}
where track_position is null or track_position < 0

