# Power BI Analytics & Reporting

This directory currently contains only this design README. Semantic models, measures, report files, and visual assets are planned for M9.

Analytical demonstrations use fully synthetic data under [ADR-0008](../docs/adr/0008-synthetic-analytics-and-source-use-boundary.md).
The responsibilities and directory structure below are targets, not current implementation.

---

## Planned Architectural Responsibility

- **Serving Curated Marts**: Power BI connects strictly to Snowflake's `MARTS` schema. It does not touch raw Landing or staging tables.
- **Star Schema Modeling**: Leverages Kimball dimensional models (`dim_track`, `dim_artist`, `dim_album`, `dim_playlist`, and `fact_playlist_snapshot`).
- **Planned Synthetic Metrics**:
  - Track lifecycle: Observed entries, exits, and days retained in simulated playlists.
  - Artist presence and share of simulated playlist positions; not audience or market share.
  - Playlist turnover, rank movement, and explicit-content share in synthetic histories.

---

## Planned Directory Structure

```
powerbi/
├── models/
│   └── semantic_model_relationships.md  # Star schema entity-relationship definitions
├── measures/
│   └── dax_measures.md                  # Curated DAX expressions (Churn, Position Changes, Retention)
├── reports/
│   └── spotify_analytics_template.pbit  # Power BI template file (no hardcoded data)
└── assets/
    └── dashboard_wireframe.png          # Visual mockup and layout wireframe
```
