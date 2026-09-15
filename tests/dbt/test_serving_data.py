"""Evaluate serving projections with tiny relational fixtures, independently of cloud.

SQLite executes the projection/join semantics; dbt parse and Snowflake live validation
remain separate gates. The two Snowflake helper functions used here have local adapters.
"""

import sqlite3
from pathlib import Path

import pytest
from jinja2 import Environment, StrictUndefined

ROOT = Path(__file__).parents[2]


class CountIf:
    def __init__(self):
        self.count = 0

    def step(self, value):
        self.count += bool(value)

    def finalize(self):
        return self.count


@pytest.fixture
def warehouse():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.create_function("startswith", 2, lambda value, prefix: value.startswith(prefix))
    db.create_aggregate("count_if", 1, CountIf)
    db.executescript("""
        create table dim_playlist(playlist_id, playlist_name);
        insert into dim_playlist values ('p1','Demo playlist'), ('p2','Unknown source');
        create table dim_track(track_id, track_name, album_pk);
        insert into dim_track values ('t1','Track one','a1');
        create table dim_album(album_pk, album_name);
        insert into dim_album values ('a1','Album one');
        create table stg_spotify_playlist_observations(
            playlist_id, snapshot_date, spotify_snapshot_id, snapshot_timestamp);
        insert into stg_spotify_playlist_observations values
            ('p1','2026-09-10','cc0-sim-p1','2026-09-10T12:00:00'),
            ('p1','2026-09-11','cc0-sim-p1','2026-09-11T12:00:00'),
            ('p2','2026-09-11','other','2026-09-11T12:00:00');
        create table mart_playlist_trends(
            playlist_id, snapshot_date, total_tracks, distinct_track_count,
            avg_duration_ms, explicit_pct, avg_release_age_years,
            new_tracks, exited_tracks, turnover_rate);
        insert into mart_playlist_trends values
            ('p1','2026-09-10',2,1,180000,null,null,null,null,null),
            ('p1','2026-09-11',0,0,null,null,null,0,1,1.0),
            ('p2','2026-09-11',1,1,200000,100.0,2.0,1,0,0.5);
        create table mart_track_lifecycle(
            playlist_id,track_id,snapshot_date,cumulative_days_on_playlist,
            current_position,best_position,position_delta);
        insert into mart_track_lifecycle values ('p1','t1','2026-09-10',1,0,0,null);
        create table mart_playlist_changes(
            playlist_id,track_id,snapshot_date,movement_status,
            current_position,previous_position,position_delta,consecutive_days_retained);
        insert into mart_playlist_changes values
            ('p1','t1','2026-09-10','NEW',0,null,null,1),
            ('p1','t1','2026-09-11','EXITED',null,0,null,1);
        create table mart_artist_presence(
            artist_id,artist_name,snapshot_date,total_tracks,distinct_playlists,
            primary_artist_tracks,featured_artist_tracks,best_observed_position,playlist_share);
        insert into mart_artist_presence values
            ('ar1','Artist one','2026-09-10',2,1,2,0,0,1.0),
            ('ar1','Artist one','2026-09-11',1,1,1,0,0,0.5);
    """)
    env = Environment(undefined=StrictUndefined)
    for name in ("bi_playlist_daily", "bi_track_daily", "bi_track_changes", "bi_artist_daily"):
        sql = (ROOT / "dbt/models/marts" / f"{name}.sql").read_text()
        rendered = env.from_string(sql).render(config=lambda **kw: "", ref=lambda name: name)
        db.execute(f"create view {name} as {rendered}")
    yield db
    db.close()


def test_serving_keeps_empty_days_unknown_attributes_and_explicit_units(warehouse):
    rows = warehouse.execute(
        "select * from bi_playlist_daily order by playlist_id,snapshot_date"
    ).fetchall()
    assert len(rows) == 3
    first, empty, unknown = rows
    assert first["playlist_name"] == "Demo playlist"
    assert first["track_slots"] == 2 and first["distinct_track_count"] == 1
    assert first["avg_duration_seconds"] == 180.0
    assert first["explicit_share"] is None
    assert first["turnover_rate"] is None
    assert empty["track_slots"] == 0 and empty["turnover_rate"] == 1.0
    assert empty["avg_duration_seconds"] is None
    assert unknown["explicit_share"] == 1.0
    assert unknown["temporal_state"] == "unclassified"


def test_track_views_preserve_exit_nulls_and_use_one_based_positions(warehouse):
    present = warehouse.execute("select * from bi_track_daily").fetchone()
    assert present["track_name"] == "Track one" and present["album_name"] == "Album one"
    assert present["current_position"] == present["best_position"] == 1
    exited = warehouse.execute(
        "select * from bi_track_changes where movement_status='EXITED'"
    ).fetchone()
    assert exited["current_position"] is None and exited["previous_position"] == 1
    assert exited["position_delta"] is None
    assert exited["temporal_state"] == "synthetic"


def test_artist_view_never_labels_mixed_dates_as_entirely_synthetic(warehouse):
    first, mixed = warehouse.execute(
        "select * from bi_artist_daily order by snapshot_date"
    ).fetchall()
    assert first["credited_track_slots"] == 2 and first["best_observed_position"] == 1
    assert first["temporal_state"] == "synthetic"
    assert mixed["temporal_state"] == "mixed_or_unclassified"
    assert mixed["playlist_share"] == 0.5
