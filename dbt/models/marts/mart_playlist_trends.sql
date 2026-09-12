with observations as (
    select
        p.playlist_pk,
        o.snapshot_date
    from {{ ref('stg_spotify_playlist_observations') }} o
    inner join {{ ref('dim_playlist') }} p
        on o.playlist_id = p.playlist_id
), slot_metrics as (
    select
        f.playlist_pk,
        f.snapshot_date,
        count(*) as total_tracks,
        count(distinct f.track_pk) as distinct_track_count,
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
), daily as (
    select
        o.playlist_pk,
        o.snapshot_date,
        coalesce(m.total_tracks, 0) as total_tracks,
        coalesce(m.distinct_track_count, 0) as distinct_track_count,
        m.avg_duration_ms,
        m.explicit_pct,
        m.avg_release_age_years
    from observations o
    left join slot_metrics m
        on o.playlist_pk = m.playlist_pk
       and o.snapshot_date = m.snapshot_date
), sequenced as (
    select
        *,
        lag(snapshot_date) over (
            partition by playlist_pk order by snapshot_date
        ) as previous_snapshot_date,
        lag(distinct_track_count) over (
            partition by playlist_pk order by snapshot_date
        ) as previous_distinct_track_count
    from daily
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
    d.snapshot_date,
    d.total_tracks,
    d.distinct_track_count,
    d.avg_duration_ms,
    d.explicit_pct,
    d.avg_release_age_years,
    case
        when d.previous_snapshot_date = dateadd(day, -1, d.snapshot_date)
            then coalesce(c.observed_new_tracks, 0)
        else null
    end as new_tracks,
    case
        when d.previous_snapshot_date = dateadd(day, -1, d.snapshot_date)
            then coalesce(c.observed_exited_tracks, 0)
        else null
    end as exited_tracks,
    case
        when d.previous_snapshot_date != dateadd(day, -1, d.snapshot_date) then null
        when d.previous_distinct_track_count + d.distinct_track_count = 0 then 0.0
        else (
            1.0 * (coalesce(c.observed_new_tracks, 0) + coalesce(c.observed_exited_tracks, 0))
        ) / (d.previous_distinct_track_count + d.distinct_track_count)
    end as turnover_rate
from sequenced d
inner join {{ ref('dim_playlist') }} p
    on d.playlist_pk = p.playlist_pk
left join change_metrics c
    on d.playlist_pk = c.playlist_pk
   and d.snapshot_date = c.snapshot_date
