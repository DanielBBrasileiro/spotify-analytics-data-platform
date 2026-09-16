"""Validate demo plans and prove exact physical file readiness before dbt."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from pathlib import Path
from uuid import UUID

DATASETS = (
    "artists",
    "albums",
    "tracks",
    "track_artists",
    "playlist_snapshots",
    "playlist_observations",
)


def run_key(airflow_run_id: str) -> str:
    return hashlib.sha256(airflow_run_id.encode()).hexdigest()[:32]


def plan_demo(manifest_path: str, start_date: str, end_date: str, airflow_run_id: str) -> dict:
    """Select a bounded window; every new Dag run gets fresh immutable physical paths.

    Task retries keep the same IDs. Replaying a date in a new Dag run never overwrites
    Parquet already tracked by Snowpipe. Bronze source content remains unchanged.
    """
    start, end = date.fromisoformat(start_date), date.fromisoformat(end_date)
    if start > end or (end - start).days > 30:
        raise ValueError("Use an ordered window of at most 31 days.")
    path = Path(manifest_path).resolve()
    manifest = json.loads(path.read_text())
    if manifest.get("source", {}).get("license") != "CC0-1.0":
        raise ValueError("This DAG accepts only the CC0 demo manifest.")
    records, identities = [], set()
    for original in manifest["records"]:
        day = date.fromisoformat(original["snapshot_date"])
        if not start <= day <= end:
            continue
        playlist_id = original["playlist_id"]
        if len(playlist_id) != 22 or not playlist_id.isascii() or not playlist_id.isalnum():
            raise ValueError("Invalid playlist ID.")
        identity = (playlist_id, day.isoformat())
        if identity in identities:
            raise ValueError("Duplicate playlist/date in demo manifest.")
        identities.add(identity)
        local_path = (path.parent / original["bronze_relative_path"]).resolve()
        if not local_path.is_relative_to(path.parent):
            raise ValueError("Bronze file must be inside the manifest directory.")
        payload = local_path.read_bytes()
        source = json.loads(payload)
        if (
            source.get("playlist_id") != playlist_id
            or source.get("spotify_snapshot_id") != original["spotify_snapshot_id"]
            or source.get("source_provenance", {}).get("temporal_state") != "synthetic"
        ):
            raise ValueError("Bronze source and manifest do not agree.")
        timestamp = datetime.fromisoformat(original["snapshot_timestamp"])
        if timestamp.tzinfo is None or timestamp.date() != day:
            raise ValueError("Snapshot timestamp must be timezone-aware and match its date.")
        date.fromisoformat(original["ingestion_date"])
        material = f"{airflow_run_id}|{playlist_id}|{day}".encode()
        physical_id = str(UUID(bytes=hashlib.sha256(material).digest()[:16], version=4))
        record = {
            key: original[key]
            for key in (
                "playlist_id",
                "snapshot_date",
                "snapshot_timestamp",
                "ingestion_date",
                "spotify_snapshot_id",
            )
        }
        record.update(
            pipeline_run_id=physical_id,
            local_path=str(local_path),
            sha256=hashlib.sha256(payload).hexdigest(),
            bronze_key=(
                f"bronze/spotify/playlist_tracks/ingestion_date={record['ingestion_date']}/"
                f"run_id={physical_id}/playlist_{playlist_id}.json"
            ),
            completion_key=f"metadata/curation/{physical_id}/complete.json",
        )
        records.append(record)
    expected_days = (end - start).days + 1
    if len({r["snapshot_date"] for r in records}) != expected_days:
        raise ValueError("Every requested day must exist in the demo manifest.")
    return {
        "run_key": run_key(airflow_run_id),
        "airflow_run_id": airflow_run_id,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "source_type": "cc0_demo",
        "temporal_state": "synthetic",
        "records": records,
    }


def validate_completion(completion: dict, record: dict) -> dict:
    """Accept only complete, run-scoped inventories emitted after successful Glue writes."""
    if completion.get("schema_version") != 1:
        raise ValueError("Unknown completion manifest version.")
    for field in ("pipeline_run_id", "playlist_id", "snapshot_date", "ingestion_date"):
        if completion.get(field) != record[field]:
            raise ValueError(f"Completion lineage mismatch: {field}.")
    datasets = completion.get("datasets", {})
    if set(datasets) != set(DATASETS):
        raise ValueError("Completion must include all six Silver datasets.")
    for dataset, files in datasets.items():
        if not files:
            raise ValueError(f"Missing Parquet inventory for {dataset}.")
        prefix = (
            f"silver/{dataset}/ingestion_date={record['ingestion_date']}/"
            f"run_id={record['pipeline_run_id']}/playlist_id={record['playlist_id']}/"
        )
        seen = set()
        for file in files:
            key, rows = file["key"], file["rows"]
            if (
                not key.startswith(prefix)
                or not key.endswith(".parquet")
                or "/" in key[len(prefix) :]
                or key in seen
                or type(rows) is not int
                or rows < 0
            ):
                raise ValueError(f"Invalid physical file contract for {dataset}.")
            seen.add(key)
    if sum(f["rows"] for f in datasets["playlist_observations"]) != 1:
        raise ValueError("A physical playlist run requires one observation.")
    if type(completion.get("rejected_items")) is not int or completion["rejected_items"] < 0:
        raise ValueError("Completion must report rejected item count.")
    return datasets


def landing_ready(expected: list[dict], landed: list[tuple]) -> bool:
    """Compare filenames, total rows and distinct row numbers; ignore unrelated runs.

    Empty Parquet is proved empty by Glue's completion inventory and needs no Landing
    row. Missing positive files wait; unexpected/duplicate rows fail closed.
    """
    counts = {file["key"].removeprefix("silver/"): file["rows"] for file in expected}
    observed = {}
    for filename, count, distinct_rows in landed:
        # Snowflake stage paths may include the silver root depending on stage setup.
        filename = filename.removeprefix("silver/")
        if filename not in counts or filename in observed:
            raise ValueError("Unexpected or repeated physical file in Landing.")
        if count != distinct_rows or count > counts[filename]:
            raise ValueError("Duplicated or excess physical rows in Landing.")
        observed[filename] = count
    return all(observed.get(name, 0) == rows for name, rows in counts.items())
