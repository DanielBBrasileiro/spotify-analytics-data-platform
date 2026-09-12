"""Offline-testable Glue 5.1 Bronze-to-Silver curation entry point.

The job deliberately accepts physical run lineage as arguments because Bronze preserves
the Spotify source envelope unchanged and does not inject pipeline telemetry fields.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from uuid import UUID

from pyspark.sql import DataFrame, SparkSession

from glue.schemas.bronze_schema import BRONZE_PLAYLIST_SNAPSHOT_SCHEMA
from glue.schemas.validation import require_no_corrupt_records
from glue.storage.parquet import write_silver_dataset
from glue.transforms.entities import (
    extract_albums,
    extract_artists,
    extract_track_artists,
    extract_tracks,
)
from glue.transforms.quarantine import rejected_playlist_items
from glue.transforms.snapshots import SnapshotLineage, extract_playlist_snapshots


@dataclass(frozen=True)
class CurationResult:
    """Deterministic outputs produced by one Bronze-to-Silver curation invocation."""

    destinations: dict[str, str]
    rejected_items: int


def read_bronze_snapshot(spark: SparkSession, path: str | Path) -> DataFrame:
    """Read immutable Bronze JSON with the explicit schema and corruption capture."""
    frame = (
        spark.read.option("multiLine", True)
        .option("mode", "PERMISSIVE")
        .option("columnNameOfCorruptRecord", "_corrupt_record")
        .schema(BRONZE_PLAYLIST_SNAPSHOT_SCHEMA)
        .json(str(path))
    )
    require_no_corrupt_records(frame)
    return frame


def build_silver_datasets(
    bronze: DataFrame,
    *,
    lineage: SnapshotLineage,
) -> tuple[dict[str, DataFrame], DataFrame]:
    """Apply only technical lake transformations; business modeling remains in dbt."""
    ingestion_date = lineage.ingestion_date
    datasets = {
        "artists": extract_artists(bronze, ingestion_date=ingestion_date),
        "albums": extract_albums(bronze, ingestion_date=ingestion_date),
        "tracks": extract_tracks(bronze, ingestion_date=ingestion_date),
        "track_artists": extract_track_artists(bronze, ingestion_date=ingestion_date),
        "playlist_snapshots": extract_playlist_snapshots(bronze, lineage=lineage),
    }
    return datasets, rejected_playlist_items(bronze)


def run_bronze_to_silver(
    spark: SparkSession,
    *,
    bronze_path: str | Path,
    silver_root: str | Path,
    lineage: SnapshotLineage,
    output_partitions: int = 1,
) -> CurationResult:
    """Read one or more Bronze snapshots and publish all canonical Silver datasets."""
    bronze = read_bronze_snapshot(spark, bronze_path)
    datasets, rejected = build_silver_datasets(bronze, lineage=lineage)
    destinations = {
        dataset: write_silver_dataset(
            frame,
            root=silver_root,
            dataset=dataset,
            ingestion_date=lineage.ingestion_date,
            output_partitions=output_partitions,
        )
        for dataset, frame in datasets.items()
    }
    return CurationResult(destinations=destinations, rejected_items=rejected.count())


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bronze-path", required=True)
    parser.add_argument("--silver-root", required=True)
    parser.add_argument("--pipeline-run-id", required=True)
    parser.add_argument("--snapshot-date", required=True)
    parser.add_argument("--snapshot-timestamp", required=True)
    parser.add_argument("--ingestion-date", required=True)
    parser.add_argument("--output-partitions", type=int, default=1)
    return parser.parse_args(argv)


def _lineage_from_args(args: argparse.Namespace) -> SnapshotLineage:
    return SnapshotLineage(
        pipeline_run_id=UUID(args.pipeline_run_id),
        snapshot_date=date.fromisoformat(args.snapshot_date),
        snapshot_timestamp=datetime.fromisoformat(args.snapshot_timestamp),
        ingestion_date=date.fromisoformat(args.ingestion_date),
    )


def main(argv: list[str] | None = None) -> int:
    """Run the curation job using a SparkSession supplied by local Spark or Glue."""
    args = _parse_args(argv)
    spark = SparkSession.builder.appName("spotify-bronze-to-silver").getOrCreate()
    try:
        run_bronze_to_silver(
            spark,
            bronze_path=args.bronze_path,
            silver_root=args.silver_root,
            lineage=_lineage_from_args(args),
            output_partitions=args.output_partitions,
        )
    finally:
        spark.stop()
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised by Spark/Glue job invocation
    raise SystemExit(main())
