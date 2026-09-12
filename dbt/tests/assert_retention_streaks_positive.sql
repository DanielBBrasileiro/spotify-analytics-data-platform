select *
from {{ ref('mart_playlist_changes') }}
where consecutive_days_retained is null or consecutive_days_retained < 1

