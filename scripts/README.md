# Utility Scripts

This directory contains developer automation, data generation, and local testing utilities.

---

## Architectural Responsibility

- **Local Mocking & Fixture Generation**: Scripts to generate synthetic Spotify JSON payloads matching API contracts for offline unit and PySpark testing.
- **Environment Bootstrapping**: Local environment setup and credential validation checks.
- **Teardown Automation**: Verification scripts ensuring zero remaining cloud resources post-demonstration.

---

## Utilities

```
scripts/
└── generate_cc0_playlist_bronze.py # Adapts a CC0 playlist CSV into a tiny three-day Bronze demo
```

`generate_cc0_playlist_bronze.py` is the public-portfolio source adapter used when live
Spotify Web API access is unavailable. It reads the CC0-licensed Kaggle dataset
`jeremycte/spotify-10000-songs-dataset`, preserves source track/artist/playlist IDs and
metadata, creates clearly namespaced deterministic album keys where the source has no album
ID, and simulates an explicitly synthetic three-day playlist evolution. The raw public
source file and generated demo remain under `tmp/`, which is ignored by Git.

Example:

```bash
.venv/bin/python scripts/generate_cc0_playlist_bronze.py \
  --csv-path tmp/spotify10000/data.csv \
  --output-root tmp/cc0-cloud-demo \
  --start-date 2026-09-10 \
  --track-limit 12
```
