"""Verify the fixture corpus independently of production item parsing."""

import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

FIXTURES = Path(__file__).parents[1] / "fixtures" / "spotify"


def walk_objects(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk_objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_objects(child)


@pytest.mark.parametrize("path", sorted(FIXTURES.glob("*.json")), ids=lambda p: p.name)
def test_fixture_json_has_no_deprecated_fields_or_credentials(path):
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    forbidden = {
        "popularity",
        "label",
        "access_token",
        "refresh_token",
        "client_secret",
        "Authorization",
    }
    for obj in walk_objects(payload):
        assert not forbidden.intersection(obj)


def test_full_page_and_tail_form_a_complete_contiguous_sequence(load_spotify_fixture):
    first = load_spotify_fixture("sample_playlist_items_response.json")
    last = load_spotify_fixture("sample_playlist_items_last_page.json")
    assert (len(first["items"]), len(last["items"])) == (50, 2)
    assert first["limit"] == last["limit"] == 50
    assert first["total"] == last["total"] == 52
    assert first["offset"] == 0
    assert last["offset"] == len(first["items"])
    assert first["next"] == last["href"]
    assert last["previous"] == first["href"]
    assert first["previous"] is None and last["next"] is None
    assert parse_qs(urlsplit(first["next"]).query) == {"limit": ["50"], "offset": ["50"]}
    assert len({entry["item"]["id"] for entry in first["items"] + last["items"]}) == 52
    assert all(
        1 <= entry["item"]["track_number"] <= entry["item"]["album"]["total_tracks"]
        for entry in first["items"] + last["items"]
    )


def test_snapshot_id_belongs_to_metadata_not_items_pages(load_spotify_fixture):
    metadata = load_spotify_fixture("sample_playlist_response.json")
    assert metadata["snapshot_id"] == "synthetic-snapshot-v1"
    for name in (
        "sample_playlist_items_response.json",
        "sample_playlist_items_last_page.json",
        "sample_playlist_items_single_page.json",
    ):
        page = load_spotify_fixture(name)
        assert "snapshot_id" not in page
        assert f"/playlists/{metadata['id']}/items" in page["href"]
        assert all("item" in entry and "track" not in entry for entry in page["items"])


def test_single_page_contains_nullable_local_and_episode_cases(load_spotify_fixture):
    page = load_spotify_fixture("sample_playlist_items_single_page.json")
    assert len(page["items"]) == page["total"] == 4
    assert page["offset"] == 0 and page["next"] is None and page["previous"] is None
    assert page["items"][0]["item"] == load_spotify_fixture("sample_multi_artist_track.json")
    assert page["items"][1] == load_spotify_fixture("sample_local_item.json")
    assert page["items"][2] == load_spotify_fixture("sample_non_track_item.json")
    assert page["items"][3]["item"] is None
    assert all(entry["added_at"] is None and entry["added_by"] is None for entry in page["items"])


def test_track_contains_album_and_ordered_artist_objects(load_spotify_fixture):
    track = load_spotify_fixture("sample_multi_artist_track.json")
    assert track["type"] == "track" and not track["is_local"]
    assert [artist["name"] for artist in track["artists"]] == [
        "Synthetic Artist 1",
        "Synthetic Artist 2",
    ]
    assert all(artist["type"] == "artist" for artist in track["artists"])
    assert track["album"]["type"] == "album"
    assert track["album"]["release_date_precision"] == "day"
    assert track["duration_ms"] > 0


def test_rate_limit_body_keeps_headers_separate(load_spotify_fixture):
    error = load_spotify_fixture("sample_rate_limit_error.json")
    assert error == {"error": {"status": 429, "message": "API rate limit exceeded"}}
    assert "Retry-After" not in error
