{{
    config(
        materialized='incremental',
        incremental_strategy='merge',
        unique_key='album_pk',
        merge_update_columns=['album_name', 'album_type', 'release_date', 'total_tracks']
    )
}}

select
    {{ dbt_utils.generate_surrogate_key(['album_id']) }} as album_pk,
    album_id,
    album_name,
    album_type,
    release_date,
    total_tracks
from {{ ref('stg_spotify_albums') }}

