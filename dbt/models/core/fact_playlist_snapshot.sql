{{
    config(
        materialized='incremental',
        incremental_strategy='merge',
        unique_key='snapshot_pk',
        cluster_by=['snapshot_date'],
        post_hook="{{ prune_snapshot_fact_after_merge() }}"
    )
}}

with source_snapshot as (
    select *
    from {{ ref('stg_spotify_playlist_snapshots') }}
    where {{ snapshot_window_predicate('snapshot_date') }}
), resolved as (
    select
        {{
            dbt_utils.generate_surrogate_key(
                ['s.playlist_id', 's.snapshot_date', 's.track_position']
            )
        }} as snapshot_pk,
        {{ dbt_utils.generate_surrogate_key(['s.playlist_id']) }} as playlist_pk,
        {{ dbt_utils.generate_surrogate_key(['s.track_id']) }} as track_pk,
        s.snapshot_date,
        s.track_position,
        s.spotify_snapshot_id,
        s.snapshot_timestamp,
        s.added_at,
        s.pipeline_run_id
    from source_snapshot s
)

select * from resolved
