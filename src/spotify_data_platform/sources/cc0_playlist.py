"""Adapt a CC0 Spotify playlist corpus to the platform's Bronze contract.

The public source provides one historical playlist membership set with Spotify track,
artist, and playlist identifiers. It does not provide a daily history, album IDs, or
the explicit-content flag. The adapter therefore preserves source values where present,
creates clearly namespaced deterministic album keys, keeps unavailable fields null, and
generates an explicitly synthetic three-day membership evolution for portfolio testing.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from spotify_data_platform.ingestion.bronze import serialize_bronze_snapshot
from spotify_data_platform.ingestion.models import PipelineRunMetadata, RunStatus

KAGGLE_DATASET_HANDLE = "jeremycte/spotify-10000-songs-dataset"
KAGGLE_SOURCE_FILE = "data.csv"
KAGGLE_LICENSE = "CC0-1.0"
TEMPORAL_PROFILE = "cc0_deterministic_three_day_v1"


class Cc0PlaylistAdapterError(ValueError):
    """The public source cannot satisfy the portfolio Bronze adapter contract."""


def _provider_id(value: str, *, field: str) -> str:
    candidate = (value or "").strip()
    if len(candidate) != 22 or not candidate.isalnum():
        raise Cc0PlaylistAdapterError(f"{field} must be a 22-character alphanumeric ID.")
    return candidate


def _stable_album_key(row: Mapping[str, str]) -> str:
    """Return a visibly adapter-generated album key when the source lacks album IDs."""
    material = "|".join(
        [
            (row.get("artist_id") or "").strip(),
            (row.get("album_name") or "").strip(),
        ]
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:20]
    return f"srcalbum_{digest}"


def load_cc0_playlist_rows(path: str | Path) -> list[dict[str, str]]:
    """Load valid rows from the CC0 playlist CSV without depending on pandas."""
    source = Path(path)
    try:
        with source.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            required = {
                "track_id",
                "playlist_id",
                "date_added",
                "track_name",
                "first_artist",
                "artist_id",
                "album_name",
                "duration_ms",
            }
            if reader.fieldnames is None or not required.issubset(reader.fieldnames):
                raise Cc0PlaylistAdapterError("CC0 playlist CSV is missing required columns.")
            rows = [dict(row) for row in reader]
    except OSError as exc:
        raise Cc0PlaylistAdapterError(f"Unable to read CC0 playlist CSV: {source}") from exc

    valid: list[dict[str, str]] = []
    for row in rows:
        try:
            _provider_id(row.get("track_id", ""), field="track_id")
            _provider_id(row.get("artist_id", ""), field="artist_id")
            _provider_id(row.get("playlist_id", ""), field="playlist_id")
            duration = int(row.get("duration_ms", ""))
        except (Cc0PlaylistAdapterError, ValueError):
            continue
        if (
            duration <= 0
            or not row.get("track_name", "").strip()
            or not row.get("first_artist", "").strip()
        ):
            continue
        valid.append(row)
    if not valid:
        raise Cc0PlaylistAdapterError("CC0 playlist CSV contains no valid rows.")
    return valid


def select_demo_playlist(
    rows: Sequence[Mapping[str, str]], *, track_limit: int
) -> tuple[str, list[dict[str, str]]]:
    """Select the lexicographically first playlist with enough unique tracks."""
    if track_limit < 6:
        raise Cc0PlaylistAdapterError("track_limit must be at least 6.")
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    seen: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        playlist_id = _provider_id(row.get("playlist_id", ""), field="playlist_id")
        track_id = _provider_id(row.get("track_id", ""), field="track_id")
        if track_id in seen[playlist_id]:
            continue
        grouped[playlist_id].append(dict(row))
        seen[playlist_id].add(track_id)

    for playlist_id in sorted(grouped):
        candidates = grouped[playlist_id]
        if len(candidates) >= track_limit + 2:
            return playlist_id, candidates
    raise Cc0PlaylistAdapterError("No playlist contains enough unique tracks for the demo.")


def temporal_track_sets(
    tracks: Sequence[Mapping[str, str]], *, track_limit: int
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    """Create deterministic NEW/RETAINED/EXITED states from one source playlist."""
    if len(tracks) < track_limit + 2:
        raise Cc0PlaylistAdapterError("At least track_limit + 2 source tracks are required.")
    base = [dict(track) for track in tracks[:track_limit]]
    donors = [dict(track) for track in tracks[track_limit : track_limit + 2]]
    first = base
    second = [base[1], base[0], *base[2:-2], donors[0], donors[1]]
    third = [*second[2:], second[0], base[-1]]
    return first, second, third


def _bronze_item(row: Mapping[str, str]) -> dict[str, Any]:
    artist_id = _provider_id(row.get("artist_id", ""), field="artist_id")
    artist = {
        "id": artist_id,
        "name": row.get("first_artist", "").strip(),
        "type": "artist",
    }
    try:
        added_at = datetime.fromisoformat(
            row.get("date_added", "").replace("Z", "+00:00")
        ).isoformat()
    except ValueError:
        added_at = None
    return {
        "added_at": added_at,
        "is_local": False,
        "item": {
            "id": _provider_id(row.get("track_id", ""), field="track_id"),
            "name": row.get("track_name", "").strip(),
            "type": "track",
            "duration_ms": int(row.get("duration_ms", "0")),
            "explicit": None,
            "is_local": False,
            "album": {
                "id": _stable_album_key(row),
                "name": (row.get("album_name") or "Unknown album").strip(),
                "album_type": None,
                "release_date": None,
                "total_tracks": None,
                "artists": [artist],
            },
            "artists": [artist],
        },
    }


def _snapshot_id(playlist_id: str, snapshot_date: date, tracks: Sequence[Mapping[str, str]]) -> str:
    material = "|".join(_provider_id(row.get("track_id", ""), field="track_id") for row in tracks)
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]
    return f"cc0-sim-{playlist_id[:8]}-{snapshot_date.isoformat()}-{digest}"


def build_bronze_snapshot(
    playlist_id: str,
    *,
    tracks: Sequence[Mapping[str, str]],
    snapshot_date: date,
) -> dict[str, Any]:
    """Map one synthetic daily state into the existing source-shaped Bronze envelope."""
    playlist_id = _provider_id(playlist_id, field="playlist_id")
    snapshot_id = _snapshot_id(playlist_id, snapshot_date, tracks)
    items = [_bronze_item(row) for row in tracks]
    page = {
        "offset": 0,
        "limit": len(items),
        "total": len(items),
        "next": None,
        "items": items,
    }
    return {
        "playlist_id": playlist_id,
        "spotify_snapshot_id": snapshot_id,
        "playlist": {
            "id": playlist_id,
            "name": f"CC0 Portfolio Playlist {playlist_id[:8]}",
            "snapshot_id": snapshot_id,
            "collaborative": False,
            "owner": {"id": "cc0-public-corpus", "display_name": "CC0 public dataset"},
        },
        "pages": [page],
        "items": items,
        "source_provenance": {
            "source_type": "public_dataset",
            "dataset": KAGGLE_DATASET_HANDLE,
            "source_file": KAGGLE_SOURCE_FILE,
            "license": KAGGLE_LICENSE,
            "temporal_state": "synthetic",
            "temporal_profile": TEMPORAL_PROFILE,
            "generated_fields": [
                "playlist.name",
                "playlist.owner",
                "spotify_snapshot_id",
                "album.id",
                "daily_membership",
                "daily_position",
            ],
            "unavailable_fields": [
                "explicit",
                "album.release_date",
                "album.album_type",
                "album.total_tracks",
            ],
        },
    }


def generate_cc0_playlist_demo_bronze(
    csv_path: str | Path,
    output_root: str | Path,
    *,
    start_date: date,
    track_limit: int = 12,
) -> dict[str, Any]:
    """Generate three tiny Bronze snapshots and a Glue lineage manifest."""
    rows = load_cc0_playlist_rows(csv_path)
    playlist_id, playlist_rows = select_demo_playlist(rows, track_limit=track_limit)
    states = temporal_track_sets(playlist_rows, track_limit=track_limit)
    output = Path(output_root)
    records: list[dict[str, Any]] = []

    for offset, tracks in enumerate(states):
        snapshot_date = start_date + timedelta(days=offset)
        snapshot_timestamp = datetime.combine(snapshot_date, time(hour=12), tzinfo=UTC)
        snapshot = build_bronze_snapshot(playlist_id, tracks=tracks, snapshot_date=snapshot_date)
        run_id = uuid4()
        metadata = PipelineRunMetadata(
            pipeline_run_id=run_id,
            spotify_snapshot_id=snapshot["spotify_snapshot_id"],
            playlist_id=playlist_id,
            snapshot_date=snapshot_date,
            snapshot_timestamp=snapshot_timestamp,
            records_extracted=len(snapshot["items"]),
            status=RunStatus.SUCCESS,
        )
        relative_path = Path(
            "bronze",
            "spotify",
            "playlist_tracks",
            f"ingestion_date={snapshot_date.isoformat()}",
            f"run_id={run_id}",
            f"playlist_{playlist_id}.json",
        )
        destination = output / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(serialize_bronze_snapshot(snapshot, metadata))
        records.append(
            {
                "playlist_id": playlist_id,
                "snapshot_date": snapshot_date.isoformat(),
                "snapshot_timestamp": snapshot_timestamp.isoformat(),
                "ingestion_date": snapshot_date.isoformat(),
                "pipeline_run_id": str(run_id),
                "spotify_snapshot_id": snapshot["spotify_snapshot_id"],
                "records_extracted": len(snapshot["items"]),
                "bronze_relative_path": relative_path.as_posix(),
            }
        )

    manifest = {
        "source": {
            "dataset": KAGGLE_DATASET_HANDLE,
            "source_file": KAGGLE_SOURCE_FILE,
            "license": KAGGLE_LICENSE,
            "temporal_profile": TEMPORAL_PROFILE,
            "note": (
                "Track/artist/playlist metadata derives from the CC0 source; daily membership, "
                "positions, snapshot IDs, playlist label/owner, and album keys are deterministic "
                "portfolio-demo adaptations."
            ),
        },
        "start_date": start_date.isoformat(),
        "track_limit": track_limit,
        "records": records,
    }
    manifest_path = output / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest
