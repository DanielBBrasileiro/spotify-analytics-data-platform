with source as (
    select
        trim(playlist_id)::varchar(64) as playlist_id,
        trim(spotify_snapshot_id)::varchar(128) as spotify_snapshot_id,
        nullif(trim(playlist_name), '')::varchar(255) as playlist_name,
        snapshot_date::date as snapshot_date,
        snapshot_timestamp::timestamp_ntz as snapshot_timestamp,
        trim(pipeline_run_id)::varchar(64) as pipeline_run_id,
        source_item_count::integer as source_item_count,
        valid_track_count::integer as valid_track_count,
        rejected_item_count::integer as rejected_item_count,
        ingestion_date::date as ingestion_date,
        _loaded_at::timestamp_ntz as _loaded_at,
        _file_name::varchar(512) as _file_name,
        _file_row_number::integer as _file_row_number
    from {{ source('landing', 'landing_playlist_observations') }}
    where playlist_id is not null
      and trim(playlist_id) <> ''
      and spotify_snapshot_id is not null
      and trim(spotify_snapshot_id) <> ''
      and playlist_name is not null
      and trim(playlist_name) <> ''
      and snapshot_date is not null
      and snapshot_timestamp is not null
      and pipeline_run_id is not null
      and trim(pipeline_run_id) <> ''
      and source_item_count >= 0
      and valid_track_count >= 0
      and rejected_item_count >= 0
      and source_item_count = valid_track_count + rejected_item_count
), slot_counts as (
    select
        trim(playlist_id)::varchar(64) as playlist_id,
        snapshot_date::date as snapshot_date,
        trim(pipeline_run_id)::varchar(64) as pipeline_run_id,
        trim(spotify_snapshot_id)::varchar(128) as spotify_snapshot_id,
        count(distinct track_position)::integer as landed_slot_count
    from {{ source('landing', 'landing_playlist_snapshots') }}
    where playlist_id is not null
      and snapshot_date is not null
      and pipeline_run_id is not null
      and spotify_snapshot_id is not null
      and track_position >= 0
    group by 1, 2, 3, 4
), complete_runs as (
    select s.*
    from source s
    left join slot_counts c
        on s.playlist_id = c.playlist_id
       and s.snapshot_date = c.snapshot_date
       and s.pipeline_run_id = c.pipeline_run_id
       and s.spotify_snapshot_id = c.spotify_snapshot_id
    where coalesce(c.landed_slot_count, 0) = s.valid_track_count
)

select
    playlist_id,
    spotify_snapshot_id,
    playlist_name,
    snapshot_date,
    snapshot_timestamp,
    pipeline_run_id,
    source_item_count,
    valid_track_count,
    rejected_item_count,
    ingestion_date,
    _loaded_at
from complete_runs
qualify row_number() over (
    partition by playlist_id, snapshot_date
    order by
        snapshot_timestamp desc,
        _loaded_at desc,
        pipeline_run_id desc,
        _file_name desc,
        _file_row_number desc
) = 1
