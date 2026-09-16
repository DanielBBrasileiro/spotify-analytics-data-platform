#!/usr/bin/env python3
"""Generate/inspect one unified pipeline run report from local Airflow evidence."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from spotify_data_platform.orchestration.reporting import (
    build_run_report,
    locate_run_directory,
    persist_run_report,
    upload_run_report,
)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--artifact-root", default="airflow/artifacts")
    group = result.add_mutually_exclusive_group()
    group.add_argument("--airflow-run-id")
    group.add_argument("--run-key")
    result.add_argument("--upload-s3", action="store_true")
    result.add_argument("--bucket", default=os.environ.get("SPOTIFY_LAKE_BUCKET"))
    result.add_argument("--json", action="store_true", dest="json_output")
    return result


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    directory = locate_run_directory(
        Path(args.artifact_root),
        airflow_run_id=args.airflow_run_id,
        run_key_value=args.run_key,
    )
    report = build_run_report(directory)
    local_path = persist_run_report(directory, report)
    remote_uri = None
    if args.upload_s3:
        if not args.bucket:
            raise SystemExit("--bucket or SPOTIFY_LAKE_BUCKET is required with --upload-s3")
        remote_uri = upload_run_report(report, args.bucket)
    if args.json_output:
        print(json.dumps(report, indent=2))
    else:
        print(f"run={report['airflow_run_id']} status={report['status']}")
        print(
            f"window={report['start_date']}..{report['end_date']} physical_runs={len(report['physical_runs'])}"
        )
        print(f"dbt_nodes_passed={report['dbt_nodes_passed']} local={local_path}")
        if remote_uri:
            print(f"s3={remote_uri}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
