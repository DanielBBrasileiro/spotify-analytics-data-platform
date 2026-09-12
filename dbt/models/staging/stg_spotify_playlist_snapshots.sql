with source as (
    select
        trim(playlist_id)::varchar(64) as playlist_id,
        trim(spotify_snapshot_id)::varchar(128) as spotify_snapshot_id,
        nullif(trim(playlist_name), '')::varchar(255) as playlist_name,
        trim(track_id)::varchar(64) as track_id,
        track_position::integer as track_position,
        added_at::timestamp_ntz as added_at,
        snapshot_date::date as snapshot_date,
        snapshot_timestamp::timestamp_ntz as snapshot_timestamp,
        trim(pipeline_run_id)::varchar(64) as pipeline_run_id,
        ingestion_date,
        _loaded_at,
        _file_name,
        _file_row_number
    from {{ source('landing', 'landing_playlist_snapshots') }}
    where playlist_id is not null
      and trim(playlist_id) <> ''
      and spotify_snapshot_id is not null
      and trim(spotify_snapshot_id) <> ''
      and playlist_name is not null
      and trim(playlist_name) <> ''
      and track_id is not null
      and trim(track_id) <> ''
      and track_position >= 0
      and snapshot_date is not null
      and pipeline_run_id is not null
      and trim(pipeline_run_id) <> ''
), run_candidates as (
    select
        playlist_id,
        snapshot_date,
        pipeline_run_id,
        spotify_snapshot_id,
        snapshot_timestamp,
        max(_loaded_at) as run_loaded_at,
        max(_file_name) as run_file_name
    from source
    group by
        playlist_id,
        snapshot_date,
        pipeline_run_id,
        spotify_snapshot_id,
        snapshot_timestamp
), winning_runs as (
    select
        playlist_id,
        snapshot_date,
        pipeline_run_id
    from run_candidates
    qualify row_number() over (
        partition by playlist_id, snapshot_date
        order by
            snapshot_timestamp desc,
            run_loaded_at desc,
            pipeline_run_id desc,
            run_file_name desc
    ) = 1
), winning_source as (
    select s.*
    from source s
    inner join winning_runs w
        on s.playlist_id = w.playlist_id
       and s.snapshot_date = w.snapshot_date
       and s.pipeline_run_id = w.pipeline_run_id
)

select
    playlist_id,
    spotify_snapshot_id,
    playlist_name,
    track_id,
    track_position,
    added_at,
    snapshot_date,
    snapshot_timestamp,
    pipeline_run_id,
    ingestion_date,
    _loaded_at
from winning_source
qualify row_number() over (
    partition by playlist_id, snapshot_date, track_position
    order by _loaded_at desc, _file_name desc, _file_row_number desc
) = 1
