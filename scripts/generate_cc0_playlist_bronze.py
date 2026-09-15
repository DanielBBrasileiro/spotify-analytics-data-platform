"""Generate the tiny CC0-backed Bronze corpus used for cloud validation."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from spotify_data_platform.sources.cc0_playlist import generate_cc0_playlist_demo_bronze


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv-path", required=True, type=Path)
    parser.add_argument("--output-root", default=Path("tmp/cc0-cloud-demo"), type=Path)
    parser.add_argument("--start-date", default="2026-09-10")
    parser.add_argument("--track-limit", default=12, type=int)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    manifest = generate_cc0_playlist_demo_bronze(
        args.csv_path,
        args.output_root,
        start_date=date.fromisoformat(args.start_date),
        track_limit=args.track_limit,
    )
    print(f"Generated {len(manifest['records'])} Bronze snapshots in {args.output_root}")
    print(f"Manifest: {args.output_root / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
