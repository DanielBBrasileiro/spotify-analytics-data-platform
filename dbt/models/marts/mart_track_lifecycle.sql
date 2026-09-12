with daily_track_presence as (
    select
        playlist_pk,
        track_pk,
        snapshot_date,
        min(track_position) as track_position
    from {{ ref('fact_playlist_snapshot') }}
    group by playlist_pk, track_pk, snapshot_date
), history as (
    select
        f.*,
        lag(snapshot_date) over (
            partition by playlist_pk, track_pk order by snapshot_date
        ) as previous_snapshot_date,
        lag(track_position) over (
            partition by playlist_pk, track_pk order by snapshot_date
        ) as previous_position,
        count(*) over (
            partition by playlist_pk, track_pk
            order by snapshot_date
            rows between unbounded preceding and current row
        ) as cumulative_days_on_playlist,
        min(track_position) over (
            partition by playlist_pk, track_pk
            order by snapshot_date
            rows between unbounded preceding and current row
        ) as best_position
    from daily_track_presence f
)

select
    p.playlist_id,
    t.track_id,
    h.snapshot_date,
    h.cumulative_days_on_playlist,
    h.track_position as current_position,
    h.best_position,
    case
        when h.previous_snapshot_date = dateadd(day, -1, h.snapshot_date)
            then h.previous_position - h.track_position
        else null
    end as position_delta
from history h
inner join {{ ref('dim_playlist') }} p
    on h.playlist_pk = p.playlist_pk
inner join {{ ref('dim_track') }} t
    on h.track_pk = t.track_pk
