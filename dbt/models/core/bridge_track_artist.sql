{{
    config(
        materialized='incremental',
        incremental_strategy='merge',
        unique_key='bridge_pk',
        merge_update_columns=['artist_order']
    )
}}

select
    {{ dbt_utils.generate_surrogate_key(['ta.track_id', 'ta.artist_id']) }} as bridge_pk,
    t.track_pk,
    a.artist_pk,
    ta.artist_order
from {{ ref('stg_spotify_track_artists') }} ta
inner join {{ ref('dim_track') }} t
    on ta.track_id = t.track_id
inner join {{ ref('dim_artist') }} a
    on ta.artist_id = a.artist_id

