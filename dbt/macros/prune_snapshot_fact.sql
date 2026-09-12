{% macro prune_snapshot_fact_after_merge() -%}
  {%- if execute and is_incremental() -%}
    delete from {{ this }} as target
    where {{ snapshot_window_predicate('target.snapshot_date') }}
      and exists (
        select 1
        from {{ ref('stg_spotify_playlist_snapshots') }} observed
        inner join {{ ref('dim_playlist') }} playlist
          on observed.playlist_id = playlist.playlist_id
        where playlist.playlist_pk = target.playlist_pk
          and observed.snapshot_date = target.snapshot_date
      )
      and not exists (
        select 1
        from {{ ref('stg_spotify_playlist_snapshots') }} source_slot
        inner join {{ ref('dim_playlist') }} source_playlist
          on source_slot.playlist_id = source_playlist.playlist_id
        where source_playlist.playlist_pk = target.playlist_pk
          and source_slot.snapshot_date = target.snapshot_date
          and source_slot.track_position = target.track_position
      )
  {%- else -%}
    select 1 where false
  {%- endif -%}
{%- endmacro %}
