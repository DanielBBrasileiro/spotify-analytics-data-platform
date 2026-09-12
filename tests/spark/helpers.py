"""Synthetic Bronze DataFrame builders shared by local Spark tests."""

import copy
import json
from pathlib import Path

from glue.schemas.bronze_schema import BRONZE_PLAYLIST_SNAPSHOT_SCHEMA

FIXTURES = Path(__file__).parents[1] / "fixtures" / "spotify"


def load_fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def bronze_payload(*, items=None):
    playlist = load_fixture("sample_playlist_response.json")
    page = load_fixture("sample_playlist_items_single_page.json")
    selected_items = copy.deepcopy(page["items"] if items is None else items)
    page = copy.deepcopy(page)
    page["items"] = copy.deepcopy(selected_items)
    page["total"] = len(selected_items)
    return {
        "playlist_id": playlist["id"],
        "spotify_snapshot_id": playlist["snapshot_id"],
        "playlist": playlist,
        "pages": [page],
        "items": selected_items,
    }


def bronze_frame(spark, *, items=None):
    return spark.createDataFrame(
        [bronze_payload(items=items)], schema=BRONZE_PLAYLIST_SNAPSHOT_SCHEMA
    )
