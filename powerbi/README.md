# Power BI Analytics & Reporting

This directory contains the semantic modeling specifications, DAX calculations, visual mockups, and documentation for the Power BI analytical dashboard.

---

## Architectural Responsibility

- **Serving Curated Marts**: Power BI connects strictly to Snowflake's `MARTS` schema. It does not touch raw Landing or staging tables.
- **Star Schema Modeling**: Leverages Kimball dimensional models (`dim_track`, `dim_artist`, `dim_album`, `dim_playlist`, and `fact_playlist_snapshot`).
- **Business Insights**:
  - Track lifecycle: Entry dates, exit dates, and days retained in top playlists.
  - Artist market share and popularity velocity over time.
  - Playlist genre stability vs. volatility metrics.

---

## Planned Directory Structure

```
powerbi/
├── models/
│   └── semantic_model_relationships.md  # Star schema entity-relationship definitions
├── measures/
│   └── dax_measures.md                  # Curated DAX expressions (Churn, Velocity, Longevity)
├── reports/
│   └── spotify_analytics_template.pbit  # Power BI template file (no hardcoded data)
└── assets/
    └── dashboard_wireframe.png          # Visual mockup and layout wireframe
```
