{{
    config(
        materialized='incremental',
        incremental_strategy='merge',
        unique_key='artist_pk',
        merge_update_columns=['artist_name']
    )
}}

select
    {{ dbt_utils.generate_surrogate_key(['artist_id']) }} as artist_pk,
    artist_id,
    artist_name,
    _loaded_at as created_at
from {{ ref('stg_spotify_artists') }}

