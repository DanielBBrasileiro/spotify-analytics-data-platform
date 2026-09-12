with source as (
    select
        trim(track_id)::varchar(64) as track_id,
        trim(artist_id)::varchar(64) as artist_id,
        artist_order::integer as artist_order,
        ingestion_date,
        _loaded_at,
        _file_name,
        _file_row_number
    from {{ source('landing', 'landing_track_artists') }}
    where track_id is not null
      and trim(track_id) <> ''
      and artist_id is not null
      and trim(artist_id) <> ''
      and artist_order >= 0
)

select
    track_id,
    artist_id,
    artist_order,
    ingestion_date,
    _loaded_at
from source
qualify row_number() over (
    partition by track_id, artist_id
    order by ingestion_date desc, _loaded_at desc, _file_name desc, _file_row_number desc
) = 1

