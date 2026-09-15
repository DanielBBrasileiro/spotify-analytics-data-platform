# Serving contract for future BI

No dashboard is part of this delivery. The public consumption surface is the four
`BI_*` views in `SPOTIFY_ANALYTICS.MARTS`; use role `SPOTIFY_ANALYST`, warehouse `COMPUTE_WH`.
Views are created by the next successful dbt build. Existing RBAC grants already cover
future MARTS views. No Power BI connection or license is required to prepare this layer.

| View | Unique row key | Main content |
| --- | --- | --- |
| BI_PLAYLIST_DAILY | playlist_id, snapshot_date | Name, slots, distinct tracks, duration, additions, exits, turnover |
| BI_TRACK_DAILY | playlist_id, track_id, snapshot_date | Track/album/playlist names, current/best position, days observed |
| BI_TRACK_CHANGES | playlist_id, track_id, snapshot_date | Names, NEW/RETAINED/EXITED, positions, retention streak |
| BI_ARTIST_DAILY | artist_id, snapshot_date | Artist name, credited slots, playlist reach and share |

## Meaning and units

- IDs are text; dates are dates. Names are descriptive labels, never join keys.
- Display positions are **one-based** in BI views. Core/marts remain zero-based. Positive
  `position_delta` means moving up; converting both positions leaves the delta unchanged.
- Duration is seconds; shares and turnover are ratios **0–1** for percentage formatting.
- `track_slots` includes a track occupying multiple positions; `distinct_track_count`
  counts unique tracks. Track-level views use the best slot per track/date.
- `cumulative_days_on_playlist` counts observed presence dates, not elapsed calendar days.
- `consecutive_days_retained` is a continuous presence streak. For EXITED rows it is the
  streak immediately before exit; `current_position` is null.
- `NEW` includes first observation and reappearance after missing observation days. It
  does not establish the real-world release/addition date.
- Empty observed days remain in playlist daily results with zero counts. Missing days
  are absent and do not imply exits. Changes need consecutive calendar-day observations.
- Turnover = `(new + exited) / (previous + current distinct tracks)`. It is null without
  a consecutive prior observation, and zero when both observed playlists are empty.

## Missing values and provenance

Unknown explicit flags and release dates remain **null**, never false or zero. Current
CC0 metadata has no explicit/release-date fields, so their measures can be unavailable.
An empty playlist also has null average duration. Future visuals should display these as
unavailable, rather than silently imputing a value.

`source_type=cc0_demo` and `temporal_state=synthetic` are derived from the canonical
`cc0-sim-` snapshot namespace. Other snapshots are `unclassified`, never automatically
asserted to be observed Spotify activity. Artist/date aggregations become
`mixed_or_unclassified` when any contributing observed playlist is unclassified.

Labels are the current dimension values, not historically versioned names. CC0 playlist
labels and album keys are generated adaptations. This is metadata and simulated playlist
history: there are no listening counts, real popularity scores, market share or genre
metrics in these views.

## Aggregation and relationships

- Counts are at the stated grain. Summing slots over dates counts slot-days, not tracks.
- Artist credits overlap across artists: summing artists can count a multi-artist slot
  more than once. `playlist_share` is reach, not a share of a partition summing to 100%.
- Do not sum daily percentages or averages. Compare dates or calculate weighted measures
  from the appropriate numerator/denominator. The views retain each daily result.
- Do not directly join the four views on date alone or create many-to-many joins between
  fact-like tables. A future BI model can derive distinct date, playlist, track and artist
  lookup tables from these views and use one-to-many, single-direction relationships.

## Refresh and quality handoff

Consume a new run only after its `run-summary.json` reports `status=success`. Airflow waits
for exact run-scoped Landing files before dbt; dbt tests enforce row keys, required labels
and row-count parity between each BI view and its source mart. A failed build does not
promise an atomic previous version of all marts; coordinate refresh using the summary.

The existing 126-node cloud validation predates these views. The new views require their
own live dbt build before being described as cloud-validated.
