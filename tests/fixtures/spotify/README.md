# Synthetic Spotify response fixtures

All names, IDs, URIs, timestamps, and descriptions were authored for offline
tests. These are not captured user responses and contain no credentials or
customer data. URLs describe API-shaped references; tests never visit them.

The corpus targets the September 2026 Development Mode shape: playlist entries
contain `item`, not the legacy `track` property. Deprecated `popularity` and album
`label` fields are absent. These are representative fixtures, not an exhaustive
API schema or evidence of live access.

| Fixture | Contract |
| --- | --- |
| `sample_playlist_response.json` | Metadata, including `snapshot_id`; represents a metadata projection without embedded items |
| `sample_playlist_items_response.json` | First page: offset 0, limit 50, 50 items, total 52 |
| `sample_playlist_items_last_page.json` | Tail: offset 50, two items, no next page |
| `sample_playlist_items_single_page.json` | Four entries: multi-artist track, local track, episode, unavailable item |
| `sample_multi_artist_track.json` | Track object with two artists in billing order and nested album |
| `sample_local_item.json` | Local entry with null track/album/artist IDs |
| `sample_non_track_item.json` | Episode entry with nested show; no track artists |
| `sample_rate_limit_error.json` | HTTP 429 body; tests supply `Retry-After` separately as a header |

The `/items` endpoint does **not** return `snapshot_id`. Tests load the separate
playlist metadata fixture to verify version consistency. The single-page fixture
is an alternative scenario, not a third page of the 52-item playlist.

Load fixtures with the `load_spotify_fixture` pytest fixture. Each call parses a
fresh object, avoiding mutable state shared between tests. Tests may copy and
modify a payload to exercise corruption or schema-drift handling.

Sources checked when creating this corpus:

- [Get Playlist Items](https://developer.spotify.com/documentation/web-api/reference/get-playlists-items)
- [Get Playlist](https://developer.spotify.com/documentation/web-api/reference/get-playlist)
- [Playlist concepts](https://developer.spotify.com/documentation/web-api/concepts/playlists)
