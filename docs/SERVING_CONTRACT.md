# Analytics Serving Contract

This document defines the stable analytical handoff exposed by `SPOTIFY_ANALYTICS.MARTS` in v1.0.0.

The serving layer is intentionally **BI-tool agnostic**. It provides four tested `BI_*` Snowflake views with consumer-safe grains, names, units, null semantics and source provenance. Power BI semantic modeling, DAX and dashboard assets are deliberately outside the release scope.

The four views were created by the live-validated dbt build and queried successfully with the `SPOTIFY_ANALYST` role after the bounded Airflow run.

---

## 1. Consumption Model

<!--
VISUAL ASSET 18
Target: docs/assets/serving/serving-consumption-model.png
Prompt: docs/assets/README.md#18--serving-consumption-model
When ready:
![Analytics Serving Consumption Model](assets/serving/serving-consumption-model.png)
-->

```text
Snowflake LANDING
      │
      ▼
dbt STAGING
      │
      ▼
CORE star schema
      │
      ▼
MARTS analytical models
      │
      ├── BI_PLAYLIST_DAILY
      ├── BI_TRACK_DAILY
      ├── BI_TRACK_CHANGES
      └── BI_ARTIST_DAILY
              │
              ▼
      Analyst / BI consumer
```

Default validated access context:

```sql
USE ROLE SPOTIFY_ANALYST;
USE WAREHOUSE COMPUTE_WH;
USE DATABASE SPOTIFY_ANALYTICS;
USE SCHEMA MARTS;
```

---

## 2. Public Views and Grain

| View | Unique row key | Primary analytical purpose |
|---|---|---|
| `BI_PLAYLIST_DAILY` | `playlist_id, snapshot_date` | Playlist size, duration, additions, exits, turnover and source provenance by observed day. |
| `BI_TRACK_DAILY` | `playlist_id, track_id, snapshot_date` | Present-track lifecycle, current/best position and cumulative observed days. |
| `BI_TRACK_CHANGES` | `playlist_id, track_id, snapshot_date` | `NEW`, `RETAINED`, `EXITED`, positional movement and retention streak. |
| `BI_ARTIST_DAILY` | `artist_id, snapshot_date` | Artist credited slots, playlist reach/share and billing-position metrics. |

The views are fact-like analytical surfaces. Their grains are not interchangeable, and joining them directly on date alone is unsafe.

---

## 3. `BI_PLAYLIST_DAILY`

**Grain:** one observed playlist per `snapshot_date`, including explicitly observed empty playlists.

Important semantics:

- `track_slots` counts occupied playlist positions; repeated tracks in multiple positions count multiple slots.
- `distinct_track_count` counts unique track IDs.
- `avg_duration_seconds` is expressed in seconds and is `NULL` for an observed empty playlist.
- `explicit_share` is a `0–1` ratio among tracks for which the explicit flag is known; it is `NULL` when the source does not provide enough information.
- `new_tracks` and `exited_tracks` require a directly preceding observed date; they are not inferred across gaps.
- `turnover_rate = (new + exited) / (previous + current distinct tracks)` and is a `0–1` ratio.
- `source_type` and `temporal_state` expose provenance directly to consumers.

---

## 4. `BI_TRACK_DAILY`

**Grain:** one present track per playlist/date.

Important semantics:

- If a track occupies more than one slot on the same date, the track-level model uses its best (lowest numeric) position while the canonical fact preserves every slot.
- `current_position` and `best_position` are **one-based** for display/consumption.
- `position_delta` is previous position minus current position; positive values mean the track moved upward.
- `position_delta` is not calculated across missing observation dates.
- `cumulative_days_on_playlist` counts observed presence dates, not elapsed calendar tenure.

---

## 5. `BI_TRACK_CHANGES`

**Grain:** one present-or-exited track per playlist/date in the change model.

`movement_status` has three accepted values:

| Status | Meaning |
|---|---|
| `NEW` | First observed presence, or reappearance after a gap. |
| `RETAINED` | Present on two directly consecutive observed calendar days. |
| `EXITED` | Present on the previous observed day but absent on the current directly consecutive day. |

`NEW` does **not** prove the real-world Spotify add timestamp. It is a statement about observations available to this platform.

For `EXITED` rows, `current_position` is `NULL`, while `consecutive_days_retained` represents the uninterrupted streak immediately before exit.

---

## 6. `BI_ARTIST_DAILY`

**Grain:** one artist per snapshot date across all observed playlists.

Important semantics:

- `credited_track_slots` counts playlist slots credited to the artist, not streams and not necessarily distinct tracks.
- Multi-artist tracks contribute credit to multiple artists, so artist totals can overlap.
- `playlist_share` is artist reach: observed playlists containing the artist divided by all observed playlists on that date.
- Because artist credits overlap, `playlist_share` across artists is not expected to sum to 100%.
- `best_observed_position` is one-based in the serving layer.
- provenance becomes `mixed_or_unclassified` if not every contributing observed playlist/date is confidently classified as the CC0 synthetic demo.

---

## 7. Position, Unit and Null Conventions

| Concept | Serving convention |
|---|---|
| Positions | One-based for consumers. Core/marts may remain zero-based internally. |
| Duration | Seconds in serving views. |
| Shares / turnover | Ratios in the range `0–1`, suitable for percentage formatting. |
| Unknown booleans | `NULL`; never silently coerced to `FALSE`. |
| Unknown release dates | `NULL`; never replaced by synthetic zero dates. |
| Empty observed playlist average | `NULL`, because an average over zero tracks is unavailable. |
| Labels | Descriptive attributes only; never stable relationship keys. |

---

## 8. Source Provenance Contract

The bounded portfolio demo deliberately separates **source metadata provenance** from **synthetic temporal behavior**.

Recognized CC0-demo snapshots expose:

```text
source_type     = cc0_demo
temporal_state  = synthetic
```

The CC0 adapter supplies catalog-style metadata, while playlist membership, positions and multi-day change behavior are generated deterministically by this repository.

Rows that do not match the recognized demo namespace are classified conservatively as `unclassified`, never automatically asserted to be observed Spotify activity.

Therefore these views must not be used to claim:

- real Spotify listening behavior;
- real popularity scores;
- market share;
- real historical playlist additions/exits for the demo dates;
- genre metrics that are not present in the source contract.

---

## 9. Aggregation Rules

Consumers should preserve the declared grains.

- Summing playlist slots across dates produces **slot-days**, not distinct tracks.
- Do not sum daily percentages or daily averages across dates.
- Use the appropriate numerator/denominator when deriving longer-window ratios.
- Do not join fact-like `BI_*` views directly on `snapshot_date` alone.
- A semantic model should derive distinct date, playlist, track and artist lookup tables and use one-to-many, single-direction relationships.
- Artist measures can overlap by design because a single slot can credit several artists.

---

## 10. Refresh and Quality Handoff

A consumer should treat a new pipeline output as refreshable only after the corresponding Airflow run records successful completion.

The handoff sequence is:

```text
Glue completion inventory
        │
        ▼
exact Snowflake Landing readiness
        │
        ▼
dbt build + tests
        │
        ▼
run-summary.json status=success
        │
        ▼
consumer refresh
```

Airflow verifies exact run-scoped files and row counts before dbt. dbt then enforces serving row-key uniqueness, required descriptive labels, accepted change states and coverage between serving views and their source marts.

A failed build does not promise an atomic previous version of every mart. Consumers should coordinate refresh from the successful run handoff rather than polling individual models independently.

---

## 11. Live Validation Evidence

The current serving contract has been exercised in the bounded cloud slice:

- the Airflow-orchestrated `dbt build` completed **152/152** nodes/tests successfully;
- the same 152/152 result was reproduced during the one-day replay;
- the canonical fact remained **36 total rows** after replay;
- the replayed date remained **12 rows / 12 unique fact grains**;
- all four `BI_*` views were queried successfully using `SPOTIFY_ANALYST`.

This supersedes older documentation that described the serving views as awaiting their first cloud validation.

---

## 12. Tooling Boundary

The data engineering release deliberately ends at this tested serving surface.

Not part of v1.0.0:

- Power BI semantic model;
- DAX measures;
- `.pbit` template;
- dashboard screenshots;
- Power BI connection validation.

Any BI tool can be attached later without changing the pipeline's core semantics, provided it follows the grains, relationship guidance, null semantics and provenance rules defined here.
