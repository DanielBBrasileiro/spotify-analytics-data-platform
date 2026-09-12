with source as (
    select
        trim(album_id)::varchar(64) as album_id,
        nullif(trim(album_name), '')::varchar(255) as album_name,
        nullif(trim(album_type), '')::varchar(32) as album_type,
        nullif(trim(release_date), '')::varchar(16) as source_release_date,
        total_tracks::integer as total_tracks,
        ingestion_date,
        _loaded_at,
        _file_name,
        _file_row_number
    from {{ source('landing', 'landing_albums') }}
    where album_id is not null
      and trim(album_id) <> ''
      and album_name is not null
      and trim(album_name) <> ''
), normalized as (
    select
        album_id,
        album_name,
        album_type,
        case
            when regexp_like(source_release_date, '^[0-9]{4}$')
                then try_to_date(source_release_date || '-01-01')
            when regexp_like(source_release_date, '^[0-9]{4}-[0-9]{2}$')
                then try_to_date(source_release_date || '-01')
            when regexp_like(source_release_date, '^[0-9]{4}-[0-9]{2}-[0-9]{2}$')
                then try_to_date(source_release_date)
            else null
        end as release_date,
        total_tracks,
        ingestion_date,
        _loaded_at,
        _file_name,
        _file_row_number
    from source
)

select
    album_id,
    album_name,
    album_type,
    release_date,
    total_tracks,
    ingestion_date,
    _loaded_at
from normalized
qualify row_number() over (
    partition by album_id
    order by ingestion_date desc, _loaded_at desc, _file_name desc, _file_row_number desc
) = 1

