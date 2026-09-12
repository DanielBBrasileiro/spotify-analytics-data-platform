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
        p.playlist_pk,
        t.track_pk,
        s.snapshot_date,
        s.track_position,
        s.spotify_snapshot_id,
        s.snapshot_timestamp,
        s.added_at,
        s.pipeline_run_id
    from source_snapshot s
    inner join {{ ref('dim_playlist') }} p
        on s.playlist_id = p.playlist_id
    inner join {{ ref('dim_track') }} t
        on s.track_id = t.track_id
)

select * from resolved
