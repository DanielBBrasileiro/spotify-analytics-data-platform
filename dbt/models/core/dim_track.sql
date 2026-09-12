{{
    config(
        materialized='incremental',
        incremental_strategy='merge',
        unique_key='track_pk',
        merge_update_columns=[
            'track_name', 'album_pk', 'duration_ms', 'is_explicit', 'updated_at'
        ]
    )
}}

select
    {{ dbt_utils.generate_surrogate_key(['t.track_id']) }} as track_pk,
    t.track_id,
    t.track_name,
    a.album_pk,
    t.duration_ms,
    t.is_explicit,
    t._loaded_at as created_at,
    t._loaded_at as updated_at
from {{ ref('stg_spotify_tracks') }} t
left join {{ ref('dim_album') }} a
    on t.album_id = a.album_id

