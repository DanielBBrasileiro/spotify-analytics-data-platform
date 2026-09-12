with source as (
    select
        trim(artist_id)::varchar(64) as artist_id,
        nullif(trim(artist_name), '')::varchar(255) as artist_name,
        ingestion_date,
        _loaded_at,
        _file_name,
        _file_row_number
    from {{ source('landing', 'landing_artists') }}
    where artist_id is not null
      and trim(artist_id) <> ''
      and artist_name is not null
      and trim(artist_name) <> ''
)

select
    artist_id,
    artist_name,
    ingestion_date,
    _loaded_at
from source
qualify row_number() over (
    partition by artist_id
    order by ingestion_date desc, _loaded_at desc, _file_name desc, _file_row_number desc
) = 1

