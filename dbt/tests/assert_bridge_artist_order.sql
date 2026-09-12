select *
from {{ ref('bridge_track_artist') }}
where artist_order is null or artist_order < 0

