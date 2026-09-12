{{
    config(
        materialized='incremental',
        incremental_strategy='merge',
        unique_key='playlist_pk',
        merge_update_columns=['playlist_name']
    )
}}

with latest_playlist as (
    select
        playlist_id,
        playlist_name
    from {{ ref('stg_spotify_playlist_observations') }}
    qualify row_number() over (
        partition by playlist_id
        order by snapshot_date desc, snapshot_timestamp desc, _loaded_at desc
    ) = 1
)

select
    {{ dbt_utils.generate_surrogate_key(['playlist_id']) }} as playlist_pk,
    playlist_id,
    playlist_name
from latest_playlist
