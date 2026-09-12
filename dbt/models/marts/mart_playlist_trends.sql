with playlist_metrics as (
    select
        f.playlist_pk,
        f.snapshot_date,
        count(*) as total_tracks,
        avg(t.duration_ms) as avg_duration_ms,
        avg(iff(t.is_explicit, 100.0, 0.0)) as explicit_pct,
        avg(
            iff(
                a.release_date is not null and a.release_date <= f.snapshot_date,
                datediff(day, a.release_date, f.snapshot_date) / 365.25,
                null
            )
        ) as avg_release_age_years
    from {{ ref('fact_playlist_snapshot') }} f
    inner join {{ ref('dim_track') }} t
        on f.track_pk = t.track_pk
    left join {{ ref('dim_album') }} a
        on t.album_pk = a.album_pk
    group by f.playlist_pk, f.snapshot_date
), playlist_dates as (
    select
        playlist_pk,
        snapshot_date,
        total_tracks,
        lag(snapshot_date) over (
            partition by playlist_pk order by snapshot_date
        ) as previous_snapshot_date,
        lag(total_tracks) over (
            partition by playlist_pk order by snapshot_date
        ) as previous_total_tracks
    from playlist_metrics
), change_metrics as (
    select
        p.playlist_pk,
        c.snapshot_date,
        count_if(c.movement_status = 'NEW') as observed_new_tracks,
        count_if(c.movement_status = 'EXITED') as observed_exited_tracks
    from {{ ref('mart_playlist_changes') }} c
    inner join {{ ref('dim_playlist') }} p
        on c.playlist_id = p.playlist_id
    group by p.playlist_pk, c.snapshot_date
)

select
    p.playlist_id,
    m.snapshot_date,
    m.total_tracks,
    m.avg_duration_ms,
    m.explicit_pct,
    m.avg_release_age_years,
    case
        when d.previous_snapshot_date = dateadd(day, -1, m.snapshot_date)
            then coalesce(c.observed_new_tracks, 0)
        else 0
    end as new_tracks,
    case
        when d.previous_snapshot_date = dateadd(day, -1, m.snapshot_date)
            then coalesce(c.observed_exited_tracks, 0)
        else 0
    end as exited_tracks,
    case
        when d.previous_snapshot_date = dateadd(day, -1, m.snapshot_date)
            then (
                coalesce(c.observed_new_tracks, 0) + coalesce(c.observed_exited_tracks, 0)
            ) / nullif(d.previous_total_tracks + m.total_tracks, 0)
        else null
    end as turnover_rate
from playlist_metrics m
inner join playlist_dates d
    on m.playlist_pk = d.playlist_pk
   and m.snapshot_date = d.snapshot_date
inner join {{ ref('dim_playlist') }} p
    on m.playlist_pk = p.playlist_pk
left join change_metrics c
    on m.playlist_pk = c.playlist_pk
   and m.snapshot_date = c.snapshot_date
