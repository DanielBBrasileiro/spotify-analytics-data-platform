#!/usr/bin/env python3
"""Safely replay one logical snapshot date through the validated Airflow DAG."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from datetime import date


def parse_date(value: str) -> str:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("date must use YYYY-MM-DD") from exc
    if parsed > date.today():
        raise argparse.ArgumentTypeError("future replay dates are not allowed")
    return parsed.isoformat()


def build_command(snapshot_date: str) -> list[str]:
    conf = json.dumps(
        {"start_date": snapshot_date, "end_date": snapshot_date}, separators=(",", ":")
    )
    return [
        "docker",
        "compose",
        "-f",
        "airflow/docker-compose.yml",
        "exec",
        "-T",
        "airflow",
        "airflow",
        "dags",
        "trigger",
        "spotify_daily_snapshot",
        "--conf",
        conf,
    ]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True, type=parse_date)
    parser.add_argument("--entity", choices=("playlist_tracks",), default="playlist_tracks")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if args.dry_run and args.execute:
        parser.error("choose --dry-run or --execute, not both")
    command = build_command(args.date)
    print(
        "Replay creates a fresh physical run_id; it does not delete or overwrite prior S3 publications."
    )
    print("command=" + shlex.join(command))
    if not args.execute:
        print("mode=dry-run")
        return 0
    subprocess.run(command, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
