with fact as (
    select
        playlist_pk,
        track_pk,
        snapshot_date,
        min(track_position) as track_position
    from {{ ref('fact_playlist_snapshot') }}
    group by playlist_pk, track_pk, snapshot_date
), playlist_dates as (
    select
        playlist_pk,
        snapshot_date,
        lag(snapshot_date) over (
            partition by playlist_pk order by snapshot_date
        ) as previous_snapshot_date
    from (
        select distinct playlist_pk, snapshot_date from fact
    )
), track_history as (
    select
        f.*,
        lag(snapshot_date) over (
            partition by playlist_pk, track_pk order by snapshot_date
        ) as previous_track_date
    from fact f
), retention_groups as (
    select
        *,
        sum(
            case
                when previous_track_date = dateadd(day, -1, snapshot_date) then 0
                else 1
            end
        ) over (
            partition by playlist_pk, track_pk
            order by snapshot_date
            rows between unbounded preceding and current row
        ) as retention_group
    from track_history
), retention_streaks as (
    select
        *,
        row_number() over (
            partition by playlist_pk, track_pk, retention_group
            order by snapshot_date
        ) as consecutive_days_retained
    from retention_groups
), current_rows as (
    select
        c.playlist_pk,
        c.track_pk,
        c.snapshot_date,
        c.track_position as current_position,
        p.track_position as previous_position,
        case
            when d.previous_snapshot_date = dateadd(day, -1, c.snapshot_date)
                 and p.track_pk is not null then 'RETAINED'
            else 'NEW'
        end as movement_status,
        case
            when d.previous_snapshot_date = dateadd(day, -1, c.snapshot_date)
                 and p.track_pk is not null
                then p.track_position - c.track_position
            else null
        end as position_delta,
        r.consecutive_days_retained
    from fact c
    inner join playlist_dates d
        on c.playlist_pk = d.playlist_pk
       and c.snapshot_date = d.snapshot_date
    left join fact p
        on c.playlist_pk = p.playlist_pk
       and c.track_pk = p.track_pk
       and p.snapshot_date = d.previous_snapshot_date
       and d.previous_snapshot_date = dateadd(day, -1, c.snapshot_date)
    inner join retention_streaks r
        on c.playlist_pk = r.playlist_pk
       and c.track_pk = r.track_pk
       and c.snapshot_date = r.snapshot_date
), exited_rows as (
    select
        d.playlist_pk,
        p.track_pk,
        d.snapshot_date,
        null::integer as current_position,
        p.track_position as previous_position,
        'EXITED' as movement_status,
        null::integer as position_delta,
        r.consecutive_days_retained
    from playlist_dates d
    inner join fact p
        on d.playlist_pk = p.playlist_pk
       and p.snapshot_date = d.previous_snapshot_date
       and d.previous_snapshot_date = dateadd(day, -1, d.snapshot_date)
    left join fact c
        on d.playlist_pk = c.playlist_pk
       and d.snapshot_date = c.snapshot_date
       and p.track_pk = c.track_pk
    inner join retention_streaks r
        on p.playlist_pk = r.playlist_pk
       and p.track_pk = r.track_pk
       and p.snapshot_date = r.snapshot_date
    where c.track_pk is null
), changes as (
    select * from current_rows
    union all
    select * from exited_rows
)

select
    p.playlist_id,
    t.track_id,
    c.snapshot_date,
    c.movement_status,
    c.current_position,
    c.previous_position,
    c.position_delta,
    c.consecutive_days_retained
from changes c
inner join {{ ref('dim_playlist') }} p
    on c.playlist_pk = p.playlist_pk
inner join {{ ref('dim_track') }} t
    on c.track_pk = t.track_pk
