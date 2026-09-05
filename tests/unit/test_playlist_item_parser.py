"""Classify raw entries without filtering, rewriting, or reordering the source."""

import copy

import pytest

from spotify_data_platform.extraction.items import (
    ItemKind,
    SpotifyItemParseException,
    parse_playlist_item,
)


def test_multi_artist_billing_is_preserved(load_spotify_fixture):
    track = load_spotify_fixture("sample_multi_artist_track.json")
    entry = {"is_local": False, "item": track}
    before = copy.deepcopy(entry)
    parsed = parse_playlist_item(entry)
    assert parsed.kind is ItemKind.TRACK
    assert parsed.artist_ids == ("0000000000000000000001", "0000000000000000000002")
    assert parsed.is_local is False
    assert entry == before


def test_local_item_retains_null_artist_slot(load_spotify_fixture):
    entry = load_spotify_fixture("sample_local_item.json")
    before = copy.deepcopy(entry)
    parsed = parse_playlist_item(entry)
    assert parsed.kind is ItemKind.TRACK
    assert parsed.is_local is True
    assert parsed.artist_ids == (None,)
    assert entry == before


def test_mixed_null_and_duplicate_artist_ids_are_not_dropped(load_spotify_fixture):
    track = load_spotify_fixture("sample_multi_artist_track.json")
    track["artists"].insert(
        1, {"id": None, "type": "artist", "name": "Synthetic Unresolved Artist"}
    )
    track["artists"].append(copy.deepcopy(track["artists"][0]))
    result = parse_playlist_item({"item": track})
    assert result.artist_ids == (
        "0000000000000000000001",
        None,
        "0000000000000000000002",
        "0000000000000000000001",
    )


def test_episode_is_not_misclassified_as_music(load_spotify_fixture):
    entry = load_spotify_fixture("sample_non_track_item.json")
    result = parse_playlist_item(entry)
    assert result.kind is ItemKind.EPISODE
    assert result.artist_ids == ()
    assert result.is_local is False


@pytest.mark.parametrize("entry", [None, {"item": None}, {"is_local": True, "item": None}])
def test_unavailable_entry_is_not_an_error(entry):
    result = parse_playlist_item(entry)
    assert result.kind is ItemKind.UNAVAILABLE
    assert result.artist_ids == ()


def test_future_type_is_explicitly_unsupported():
    entry = {"item": {"type": "future-media", "future_field": [1, 2]}}
    before = copy.deepcopy(entry)
    result = parse_playlist_item(entry)
    assert result.kind is ItemKind.UNSUPPORTED
    assert result.artist_ids == ()
    assert entry == before


def test_local_flag_on_track_and_empty_artists_are_supported():
    result = parse_playlist_item({"item": {"type": "track", "is_local": True, "artists": []}})
    assert result.is_local is True and result.artist_ids == ()


@pytest.mark.parametrize(
    "entry",
    [
        [],
        "raw-secret",
        42,
        {},
        {"track": {"type": "track"}},
        {"item": []},
        {"item": "raw-secret"},
        {"item": {}},
        {"item": {"type": None}},
        {"item": {"type": " "}},
        {"item": {"type": 1}},
        {"item": None, "is_local": "false"},
        {"item": None, "is_local": 0},
        {"item": {"type": "track", "is_local": None, "artists": []}},
        {"item": {"type": "track"}},
        {"item": {"type": "track", "artists": None}},
        {"item": {"type": "track", "artists": {}}},
        {"item": {"type": "track", "artists": [None]}},
        {"item": {"type": "track", "artists": [{}]}},
        {"item": {"type": "track", "artists": [{"id": 42}]}},
        {"item": {"type": "track", "artists": [{"id": ""}]}},
    ],
)
def test_malformed_shapes_raise_sanitized_domain_error(entry):
    with pytest.raises(SpotifyItemParseException) as error:
        parse_playlist_item(entry)
    assert "raw-secret" not in str(error.value)


def test_every_single_page_entry_is_classified(load_spotify_fixture):
    page = load_spotify_fixture("sample_playlist_items_single_page.json")
    assert [parse_playlist_item(entry).kind for entry in page["items"]] == [
        ItemKind.TRACK,
        ItemKind.TRACK,
        ItemKind.EPISODE,
        ItemKind.UNAVAILABLE,
    ]
