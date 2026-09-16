# Utility Scripts

The scripts in this directory support reproducible demo data, run-evidence inspection,
read-only Landing diagnosis, and safe single-date replay. Recovery scripts default to
inspection/dry-run behavior where an accidental execution would be costly.

---

## Available Utilities

```text
scripts/
├── audit_landing_lag.py           # Read-only bounded Snowflake COPY_HISTORY audit
├── generate_cc0_playlist_bronze.py # CC0 metadata -> bounded synthetic Bronze demo
├── generate_run_report.py         # Consolidate Airflow/Glue/Landing/dbt run evidence
└── replay_partition.py            # Dry-run-first single-date Airflow replay
```

---

## `generate_cc0_playlist_bronze.py`

This is the public-portfolio source adapter used when live Spotify Web API extraction is not
available or intentionally outside the validation boundary. It reads the CC0-licensed Kaggle
dataset `jeremycte/spotify-10000-songs-dataset`, preserves available source track/artist/
playlist metadata, creates deterministic namespaced album keys where the source lacks album
IDs, and simulates an explicitly synthetic three-day playlist evolution.

The licensing/provenance boundary matters: source catalog metadata is CC0-backed, while the
multi-day playlist history is generated for the demo. Generated raw/demo files remain under
`tmp/`, which is ignored by Git.

Example:

```bash
.venv/bin/python scripts/generate_cc0_playlist_bronze.py \
  --csv-path tmp/spotify10000/data.csv \
  --output-root tmp/cc0-cloud-demo \
  --start-date 2026-09-10 \
  --track-limit 12
```

Do not describe this generated history as observed Spotify activity.

---

## `generate_run_report.py`

This utility reads one completed Airflow artifact directory and builds the schema-v1 unified
`pipeline-run-report.json` defined in [`docs/OBSERVABILITY.md`](../docs/OBSERVABILITY.md).
It aggregates the persisted Airflow plan/summary, Glue run/completion evidence, exact Landing
readiness, and dbt summary.

Generate a report for the latest completed local run:

```bash
.venv/bin/python scripts/generate_run_report.py
```

Select the run explicitly when comparing retries/replays:

```bash
.venv/bin/python scripts/generate_run_report.py \
  --run-key '<run-key>' \
  --json
```

or:

```bash
.venv/bin/python scripts/generate_run_report.py \
  --airflow-run-id 'manual__example' \
  --json
```

Local generation persists `pipeline-run-report.json` next to the source evidence. S3 upload is
opt-in:

```bash
export SPOTIFY_LAKE_BUCKET='<lake-bucket-name>'
.venv/bin/python scripts/generate_run_report.py --upload-s3
```

The remote path is `s3://<bucket>/metadata/pipeline_runs/<run_key>.json`. Publication uses an
immutable conditional write; an existing object with the same key is not overwritten.

The report includes `records_extracted`, but its meaning is source-scoped. For the current
`source_type=cc0_demo` path it is the number of items already present in the generated Bronze
payload; it is **not** evidence of a live Spotify Lambda extraction. Live Lambda extraction
counts remain independently evidenced by the structured source telemetry contract.

---

## `audit_landing_lag.py`

This utility inspects Snowflake `INFORMATION_SCHEMA.COPY_HISTORY` for the six Landing tables:

- `LANDING_ARTISTS`
- `LANDING_ALBUMS`
- `LANDING_TRACKS`
- `LANDING_TRACK_ARTISTS`
- `LANDING_PLAYLIST_SNAPSHOTS`
- `LANDING_PLAYLIST_OBSERVATIONS`

The lookback is bounded to 1–168 hours. `--dry-run` prints the SQL and does not connect to
Snowflake:

```bash
.venv/bin/python scripts/audit_landing_lag.py --hours 24 --dry-run
```

For a real read-only audit, configure non-secret connection values and use key-pair auth or a
locally prompted password. Do not paste the password into a command:

```bash
export SNOWFLAKE_ACCOUNT='<account-identifier>'
export SNOWFLAKE_USER='<service-user>'
export SNOWFLAKE_ROLE='SPOTIFY_TRANSFORMER'
export SNOWFLAKE_WAREHOUSE='COMPUTE_WH'

printf 'Snowflake password: ' >&2
IFS= read -r -s SNOWFLAKE_PASSWORD
printf '\n' >&2
export SNOWFLAKE_PASSWORD

.venv/bin/python scripts/audit_landing_lag.py --hours 24
unset SNOWFLAKE_PASSWORD
```

If `SNOWFLAKE_PRIVATE_KEY_PATH` is set, the script uses key-pair authentication instead of
`SNOWFLAKE_PASSWORD`. An optional `SNOWFLAKE_PRIVATE_KEY_PASSPHRASE` can be supplied through
the local environment when the key is encrypted.

This script only reads COPY history. It does not run `COPY INTO`, delete data, resume a
warehouse explicitly, or repair a stalled load.

---

## `replay_partition.py`

This is the supported incident-recovery entry point for replaying one logical snapshot date
through the validated `spotify_daily_snapshot` Airflow DAG. It accepts dates in `YYYY-MM-DD`
format, rejects future dates, and currently supports only the `playlist_tracks` entity.

Dry-run is the default:

```bash
.venv/bin/python scripts/replay_partition.py \
  --date 2026-09-10 \
  --entity playlist_tracks
```

The output states `mode=dry-run` and prints the exact `docker compose ... airflow dags trigger`
command. `--dry-run` can be supplied explicitly:

```bash
.venv/bin/python scripts/replay_partition.py \
  --date 2026-09-10 \
  --entity playlist_tracks \
  --dry-run
```

Only `--execute` starts the DAG:

```bash
.venv/bin/python scripts/replay_partition.py \
  --date 2026-09-10 \
  --entity playlist_tracks \
  --execute
```

The replay does not delete prior publications. The new DAG run derives fresh physical
`pipeline_run_id` values and writes to new immutable run-scoped paths, while the logical
snapshot date stays the same. dbt then merges on the canonical business grain rather than the
physical run ID.

### Safe replay workflow

1. Run `replay_partition.py` without `--execute` and inspect the printed Airflow command.
2. Use `audit_landing_lag.py --dry-run` if the incident involves Snowpipe/Landing delay.
3. Investigate any ambiguous Glue submission before replaying; do not blindly clear/retry the
   Glue submission task against the same physical prefix.
4. Confirm AWS/Snowflake non-secret settings and local credential handling.
5. Re-run `replay_partition.py ... --execute` for exactly one date.
6. Wait for the normal Glue completion, exact six-dataset Landing gate, and dbt build.
7. Generate `pipeline-run-report.json` for the new run and compare it with the failed/prior
   attempt using logical date, source version, row counts, and status.

For incident details and credential-safe recovery procedures, see
[`docs/RUNBOOK.md`](../docs/RUNBOOK.md).
