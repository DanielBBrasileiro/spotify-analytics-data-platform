"""Inspect playlist item types without transforming raw ingestion payloads."""

from dataclasses import dataclass
from enum import StrEnum


class SpotifyItemParseException(ValueError):
    """An entry has an invalid shape; messages exclude raw source values."""


class ItemKind(StrEnum):
    """Explicit classification of supported, unavailable, and future media."""

    TRACK = "track"
    EPISODE = "episode"
    UNAVAILABLE = "unavailable"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class ParsedPlaylistItem:
    """Small inspection result; artist tuple order matches upstream billing."""

    kind: ItemKind
    is_local: bool = False
    artist_ids: tuple[str | None, ...] = ()


def parse_playlist_item(entry: object) -> ParsedPlaylistItem:
    """Classify a 2026 ``item`` wrapper, preserving null and duplicate artists.

    A null entry or null item is unavailable, whereas missing keys and malformed
    containers are errors. Unknown media types are explicitly unsupported. This
    opt-in parser never mutates input or filters entries from the raw extractor;
    full schema enforcement and dimensional transformations belong downstream.
    """
    if entry is None:
        return ParsedPlaylistItem(ItemKind.UNAVAILABLE)
    if not isinstance(entry, dict) or "item" not in entry:
        raise SpotifyItemParseException("Expected a playlist entry with an item field.")
    local = entry.get("is_local", False)
    if type(local) is not bool:
        raise SpotifyItemParseException("Entry is_local must be a boolean when present.")
    item = entry["item"]
    if item is None:
        return ParsedPlaylistItem(ItemKind.UNAVAILABLE, local)
    if not isinstance(item, dict):
        raise SpotifyItemParseException("Expected an item object or null.")
    item_type = item.get("type")
    if not isinstance(item_type, str) or not item_type.strip():
        raise SpotifyItemParseException("Item type must be a non-empty string.")
    item_local = item.get("is_local", False)
    if type(item_local) is not bool:
        raise SpotifyItemParseException("Item is_local must be a boolean when present.")
    local = local or item_local
    if item_type == "episode":
        return ParsedPlaylistItem(ItemKind.EPISODE, local)
    if item_type != "track":
        return ParsedPlaylistItem(ItemKind.UNSUPPORTED, local)
    artists = item.get("artists")
    if not isinstance(artists, list):
        raise SpotifyItemParseException("Track artists must be an array.")
    artist_ids: list[str | None] = []
    for artist in artists:
        if not isinstance(artist, dict) or "id" not in artist:
            raise SpotifyItemParseException("Each artist must be an object with an id field.")
        artist_id = artist["id"]
        if artist_id is not None and (not isinstance(artist_id, str) or not artist_id.strip()):
            raise SpotifyItemParseException("Artist id must be a non-empty string or null.")
        artist_ids.append(artist_id)
    return ParsedPlaylistItem(ItemKind.TRACK, local, tuple(artist_ids))
