# Future BI consumer

A Power BI dashboard, `.pbix`/`.pbit`, DAX model and Power BI deployment are **deferred**.
The current delivery prepares data for consumption through four dbt-managed views in
`SPOTIFY_ANALYTICS.MARTS`, using the existing read-only `SPOTIFY_ANALYST` role:

- `BI_PLAYLIST_DAILY`: playlist/date composition and turnover.
- `BI_TRACK_DAILY`: track/playlist/date positions and observed tenure.
- `BI_TRACK_CHANGES`: entries, retained tracks and exits.
- `BI_ARTIST_DAILY`: artist/date representation and playlist reach.

Names and labels are supplied by the views; future consumers do not need access to CORE
or LANDING. See [the serving contract](../docs/SERVING_CONTRACT.md) for keys, units, nulls,
aggregation rules and the successful-run refresh handoff.
