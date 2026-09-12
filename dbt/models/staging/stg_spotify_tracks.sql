with source as (
    select
        trim(track_id)::varchar(64) as track_id,
        nullif(trim(track_name), '')::varchar(255) as track_name,
        nullif(trim(album_id), '')::varchar(64) as album_id,
        duration_ms::integer as duration_ms,
        is_explicit::boolean as is_explicit,
        is_local::boolean as is_local,
        ingestion_date,
        _loaded_at,
        _file_name,
        _file_row_number
    from {{ source('landing', 'landing_tracks') }}
    where track_id is not null
      and trim(track_id) <> ''
      and track_name is not null
      and trim(track_name) <> ''
      and duration_ms > 0
)

select
    track_id,
    track_name,
    album_id,
    duration_ms,
    is_explicit,
    is_local,
    ingestion_date,
    _loaded_at
from source
qualify row_number() over (
    partition by track_id
    order by ingestion_date desc, _loaded_at desc, _file_name desc, _file_row_number desc
) = 1

