select
    playlist_pk,
    snapshot_date,
    track_position,
    count(*) as row_count
from {{ ref('fact_playlist_snapshot') }}
group by playlist_pk, snapshot_date, track_position
having count(*) > 1

