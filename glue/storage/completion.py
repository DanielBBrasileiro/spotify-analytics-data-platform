"""Publish an inventory only after all six immutable run outputs have been written."""

import json
from pathlib import Path
from urllib.parse import urlparse


def build_completion(spark, result, lineage, playlist_id):
    datasets = {}
    for dataset, destination in result.destinations.items():
        files = spark.read.parquet(destination).inputFiles()
        inventory = []
        for uri in sorted(files):
            parsed = urlparse(uri)
            # Works for both local test output and the S3 lake root.
            key = "silver/" + parsed.path.split("/silver/", 1)[1]
            inventory.append({"key": key, "rows": spark.read.parquet(uri).count()})
        datasets[dataset] = inventory
    return {
        "schema_version": 1,
        "pipeline_run_id": str(lineage.pipeline_run_id),
        "playlist_id": playlist_id,
        "snapshot_date": lineage.snapshot_date.isoformat(),
        "ingestion_date": lineage.ingestion_date.isoformat(),
        "rejected_items": result.rejected_items,
        "datasets": datasets,
    }


def publish_completion(uri, manifest):
    body = (json.dumps(manifest, sort_keys=True) + "\n").encode()
    parsed = urlparse(uri)
    if parsed.scheme == "s3":
        import boto3

        boto3.client("s3").put_object(
            Bucket=parsed.netloc,
            Key=parsed.path.lstrip("/"),
            Body=body,
            ContentType="application/json",
            IfNoneMatch="*",
        )
    elif not parsed.scheme:
        path = Path(uri)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Refuse to replace evidence from a previously completed physical run.
        with path.open("xb") as handle:
            handle.write(body)
    else:
        raise ValueError("Completion URI must be local or s3://.")
