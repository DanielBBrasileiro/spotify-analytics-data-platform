"""Offline manifest/static guards for the M5 dbt project."""

import json
from pathlib import Path

ROOT = Path(__file__).parents[2]
DBT = ROOT / "dbt"
MANIFEST = DBT / "target" / "manifest.json"


def _manifest():
    assert MANIFEST.exists(), "run dbt parse before the dbt contract tests"
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _model(manifest, name):
    key = f"model.spotify_analytics.{name}"
    assert key in manifest["nodes"], f"missing dbt model {name}"
    return manifest["nodes"][key]


def test_manifest_contains_complete_m5_model_set_and_layer_materializations():
    manifest = _manifest()
    expected = {
        "stg_spotify_artists": "view",
        "stg_spotify_albums": "view",
        "stg_spotify_tracks": "view",
        "stg_spotify_track_artists": "view",
        "stg_spotify_playlist_snapshots": "view",
        "dim_artist": "incremental",
        "dim_album": "incremental",
        "dim_track": "incremental",
        "dim_playlist": "incremental",
        "bridge_track_artist": "incremental",
        "fact_playlist_snapshot": "incremental",
        "mart_artist_presence": "table",
        "mart_playlist_trends": "table",
        "mart_track_lifecycle": "table",
        "mart_playlist_changes": "table",
    }
    for name, materialized in expected.items():
        assert _model(manifest, name)["config"]["materialized"] == materialized


def test_fact_incremental_contract_preserves_canonical_grain_and_backfill_strategy():
    fact = _model(_manifest(), "fact_playlist_snapshot")
    config = fact["config"]
    assert config["incremental_strategy"] == "merge"
    assert config["unique_key"] == "snapshot_pk"
    assert config["cluster_by"] == ["snapshot_date"]
    hooks = "\n".join(
        hook["sql"] if isinstance(hook, dict) else str(hook) for hook in config["post-hook"]
    )
    assert "prune_snapshot_fact_after_merge" in hooks
    raw = fact["raw_code"]
    surrogate = raw.split("as snapshot_pk", 1)[0]
    for field in ("s.playlist_id", "s.snapshot_date", "s.track_position"):
        assert field in surrogate
    assert "snapshot_timestamp" not in surrogate
    assert "max(snapshot_date)" not in raw.lower()
    assert "snapshot_window_predicate" in raw


def test_snapshot_staging_selects_one_winning_run_before_slot_deduplication():
    raw = _model(_manifest(), "stg_spotify_playlist_snapshots")["raw_code"].lower()
    assert "run_candidates" in raw
    assert "winning_runs" in raw
    assert "partition by playlist_id, snapshot_date" in raw
    winning_section = raw.split("winning_runs as", 1)[1].split("winning_source as", 1)[0]
    assert "pipeline_run_id" in winning_section
    assert "snapshot_timestamp desc" in winning_section
    assert "partition by playlist_id, snapshot_date, track_position" not in winning_section


def test_fact_cleanup_is_scoped_and_removes_only_slots_missing_from_winning_source():
    macro = (DBT / "macros" / "prune_snapshot_fact.sql").read_text(encoding="utf-8").lower()
    assert "if execute and is_incremental()" in macro
    assert "snapshot_window_predicate('target.snapshot_date')" in macro
    assert "exists (" in macro
    assert "not exists (" in macro
    assert "source_slot.track_position = target.track_position" in macro
    assert "observed.snapshot_date = target.snapshot_date" in macro


def test_dbt_project_has_no_compile_time_warehouse_introspection_or_privileged_profile():
    project_sql = "\n".join(
        path.read_text(encoding="utf-8")
        for path in DBT.rglob("*.sql")
        if "dbt_packages" not in path.parts and "target" not in path.parts
    ).lower()
    for forbidden in ("run_query(", "statement(", "load_relation(", "adapter.get_relation"):
        assert forbidden not in project_sql
    assert "popularity" not in project_sql
    assert " label " not in project_sql

    profiles = (DBT / "profiles.yml.example").read_text(encoding="utf-8")
    assert "SPOTIFY_TRANSFORMER" in profiles
    assert "SYSADMIN" not in profiles and "ACCOUNTADMIN" not in profiles
    for secret in ("SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_PASSWORD"):
        assert f"env_var('{secret}')" in profiles


def test_pinned_packages_and_versions_are_reproducible():
    requirements = (DBT / "requirements-dev.txt").read_text(encoding="utf-8")
    packages = (DBT / "packages.yml").read_text(encoding="utf-8")
    lock = (DBT / "package-lock.yml").read_text(encoding="utf-8")
    assert "dbt-core==1.12.4" in requirements
    assert "dbt-snowflake==1.12.0" in requirements
    assert "version: 1.4.1" in packages
    assert "version: 1.4.1" in lock


def test_manifest_sources_are_exactly_the_five_landing_contracts():
    sources = {
        node["name"]
        for node in _manifest()["sources"].values()
        if node.get("source_name") == "landing"
    }
    assert sources == {
        "landing_artists",
        "landing_albums",
        "landing_tracks",
        "landing_track_artists",
        "landing_playlist_snapshots",
    }


def test_dim_playlist_does_not_invent_unavailable_source_attributes():
    raw = _model(_manifest(), "dim_playlist")["raw_code"].lower()
    assert "owner_id" not in raw
    assert "is_collaborative" not in raw
    assert "playlist_id" in raw and "playlist_name" in raw


def test_mart_change_model_requires_consecutive_dates_for_retention_and_exits():
    raw = _model(_manifest(), "mart_playlist_changes")["raw_code"].lower()
    assert raw.count("dateadd(day, -1") >= 3
    assert "'retained'" in raw
    assert "'exited'" in raw
    assert "retention_group" in raw


def test_snapshot_window_macro_fails_closed_for_real_execution_without_max_watermark():
    macro = (DBT / "macros" / "snapshot_window.sql").read_text(encoding="utf-8").lower()
    assert "if execute" in macro
    assert macro.count("raise_compiler_error") >= 4
    assert "snapshot_date" in macro
    assert "start_date" in macro and "end_date" in macro
    assert "max(snapshot_date)" not in macro


def test_singular_quality_suite_is_registered_in_manifest():
    manifest = _manifest()
    test_names = {
        node["name"] for node in manifest["nodes"].values() if node.get("resource_type") == "test"
    }
    expected = {
        "assert_positive_track_durations",
        "assert_nonnegative_positions",
        "assert_fact_snapshot_grain",
        "assert_bridge_artist_order",
        "assert_playlist_change_continuity",
        "assert_mart_numeric_bounds",
        "assert_retention_streaks_positive",
    }
    assert expected <= test_names
