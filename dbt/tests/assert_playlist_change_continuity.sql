with changes as (
    select
        c.*,
        p.playlist_pk,
        t.track_pk
    from {{ ref('mart_playlist_changes') }} c
    inner join {{ ref('dim_playlist') }} p
        on c.playlist_id = p.playlist_id
    inner join {{ ref('dim_track') }} t
        on c.track_id = t.track_id
), evaluated as (
    select
        c.*,
        exists (
            select 1
            from {{ ref('fact_playlist_snapshot') }} previous
            where previous.playlist_pk = c.playlist_pk
              and previous.track_pk = c.track_pk
              and previous.snapshot_date = dateadd(day, -1, c.snapshot_date)
        ) as existed_yesterday,
        exists (
            select 1
            from {{ ref('fact_playlist_snapshot') }} current_day
            where current_day.playlist_pk = c.playlist_pk
              and current_day.track_pk = c.track_pk
              and current_day.snapshot_date = c.snapshot_date
        ) as exists_today
    from changes c
)

select *
from evaluated
where (movement_status = 'RETAINED' and not (existed_yesterday and exists_today))
   or (movement_status = 'NEW' and existed_yesterday)
   or (movement_status = 'EXITED' and not (existed_yesterday and not exists_today))

