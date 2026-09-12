select *
from {{ ref('dim_track') }}
where duration_ms is null or duration_ms <= 0

