from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

import pytest

from spotify_data_platform.sources.cc0_playlist import (
    Cc0PlaylistAdapterError,
    build_bronze_snapshot,
    generate_cc0_playlist_demo_bronze,
    load_cc0_playlist_rows,
    temporal_track_sets,
)


def _row(number: int, *, playlist_id: str = "P" * 22) -> dict[str, str]:
    return {
        "track_id": f"{number:022d}",
        "playlist_id": playlist_id,
        "date_added": "2021-08-08T09:26:31Z",
        "track_name": f"Track {number}",
        "first_artist": f"Artist {number}",
        "artist_id": f"{number + 1000:022d}",
        "album_name": f"Album {number // 2}",
        "duration_ms": str(180_000 + number),
    }


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_load_cc0_playlist_rows_filters_invalid_provider_ids(tmp_path: Path) -> None:
    valid = _row(1)
    invalid = _row(2)
    invalid["track_id"] = "bad"
    path = tmp_path / "data.csv"
    _write_csv(path, [valid, invalid])

    assert load_cc0_playlist_rows(path) == [valid]


def test_temporal_track_sets_create_new_retained_exited_and_position_changes() -> None:
    rows = [_row(index) for index in range(14)]
    day1, day2, day3 = temporal_track_sets(rows, track_limit=12)

    def ids(items: list[dict[str, str]]) -> list[str]:
        return [row["track_id"] for row in items]

    day1_ids, day2_ids, day3_ids = map(ids, (day1, day2, day3))
    assert len(day1_ids) == len(day2_ids) == len(day3_ids) == 12
    assert len(set(day1_ids) - set(day2_ids)) == 2
    assert len(set(day2_ids) - set(day1_ids)) == 2
    assert len(set(day2_ids) - set(day3_ids)) == 1
    assert len(set(day3_ids) - set(day2_ids)) == 1
    assert day2_ids[:2] == day1_ids[1::-1]


def test_build_bronze_snapshot_marks_generated_and_unavailable_fields() -> None:
    playlist_id = "P" * 22
    snapshot = build_bronze_snapshot(
        playlist_id,
        tracks=[_row(index, playlist_id=playlist_id) for index in range(6)],
        snapshot_date=date(2026, 9, 10),
    )

    first = snapshot["items"][0]
    assert first["item"]["id"] == "0000000000000000000000"
    assert first["item"]["explicit"] is None
    assert first["item"]["album"]["id"].startswith("srcalbum_")
    assert first["added_at"] == "2021-08-08T09:26:31+00:00"
    assert snapshot["source_provenance"]["license"] == "CC0-1.0"
    assert "album.id" in snapshot["source_provenance"]["generated_fields"]


def test_generate_cc0_playlist_demo_writes_three_bronze_snapshots(tmp_path: Path) -> None:
    path = tmp_path / "data.csv"
    rows = [_row(index) for index in range(14)]
    _write_csv(path, rows)
    output = tmp_path / "generated"

    manifest = generate_cc0_playlist_demo_bronze(
        path, output, start_date=date(2026, 9, 10), track_limit=12
    )

    assert len(manifest["records"]) == 3
    assert manifest["source"]["license"] == "CC0-1.0"
    assert [record["snapshot_date"] for record in manifest["records"]] == [
        "2026-09-10",
        "2026-09-11",
        "2026-09-12",
    ]
    for record in manifest["records"]:
        payload = json.loads((output / record["bronze_relative_path"]).read_text())
        assert len(payload["items"]) == 12
        assert payload["playlist_id"] == "P" * 22


def test_temporal_track_sets_requires_two_donors() -> None:
    with pytest.raises(Cc0PlaylistAdapterError, match=r"track_limit \+ 2"):
        temporal_track_sets([_row(index) for index in range(13)], track_limit=12)
