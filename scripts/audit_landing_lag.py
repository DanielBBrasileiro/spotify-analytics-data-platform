#!/usr/bin/env python3
"""Inspect bounded Snowpipe COPY history without changing warehouse data."""

from __future__ import annotations

import argparse
import os

TABLES = (
    "LANDING_ARTISTS",
    "LANDING_ALBUMS",
    "LANDING_TRACKS",
    "LANDING_TRACK_ARTISTS",
    "LANDING_PLAYLIST_SNAPSHOTS",
    "LANDING_PLAYLIST_OBSERVATIONS",
)


def copy_history_sql(table: str, hours: int) -> str:
    if table not in TABLES:
        raise ValueError("unsupported Landing table")
    if not 1 <= hours <= 168:
        raise ValueError("hours must be between 1 and 168")
    return f"""SELECT file_name, last_load_time, status, row_count, row_parsed
FROM TABLE(SPOTIFY_ANALYTICS.INFORMATION_SCHEMA.COPY_HISTORY(
  TABLE_NAME=>'LANDING.{table}',
  START_TIME=>DATEADD('hour', -{hours}, CURRENT_TIMESTAMP())
))
ORDER BY last_load_time DESC"""


def _connection():
    import snowflake.connector

    auth = {}
    private_key = os.environ.get("SNOWFLAKE_PRIVATE_KEY_PATH")
    if private_key:
        auth["private_key_file"] = private_key
        if os.environ.get("SNOWFLAKE_PRIVATE_KEY_PASSPHRASE"):
            auth["private_key_file_pwd"] = os.environ["SNOWFLAKE_PRIVATE_KEY_PASSPHRASE"]
    else:
        auth["password"] = os.environ["SNOWFLAKE_PASSWORD"]
    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        role=os.environ.get("SNOWFLAKE_ROLE", "SPOTIFY_TRANSFORMER"),
        warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
        database="SPOTIFY_ANALYTICS",
        schema="LANDING",
        **auth,
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hours", type=int, default=24)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if not 1 <= args.hours <= 168:
        parser.error("--hours must be between 1 and 168")
    if args.dry_run:
        for table in TABLES:
            print(f"-- {table}\n{copy_history_sql(table, args.hours)};\n")
        return 0
    with _connection() as connection, connection.cursor() as cursor:
        for table in TABLES:
            cursor.execute(copy_history_sql(table, args.hours))
            rows = cursor.fetchall()
            print(f"{table}: files={len(rows)}")
            for file_name, loaded_at, status, row_count, row_parsed in rows[:10]:
                print(f"  {loaded_at} {status} rows={row_count}/{row_parsed} {file_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
