"""Offline structural contracts for Snowflake M4 SQL without any account connection."""

import re
from pathlib import Path

ROOT = Path(__file__).parents[2]
SNOWFLAKE = ROOT / "snowflake"
DDL = SNOWFLAKE / "ddl"


def _read(name: str) -> str:
    return (DDL / name).read_text(encoding="utf-8")


def test_required_m4_sql_assets_exist():
    expected = {
        "01_databases_and_schemas.sql",
        "02_rbac_roles_and_grants.sql",
        "02a_compute_cost_guardrails.sql",
        "03_storage_integration.sql",
        "04_external_stages.sql",
        "05_file_formats.sql",
        "06_landing_tables.sql",
        "07_snowpipes.sql",
    }
    assert expected <= {path.name for path in DDL.glob("*.sql")}


def test_topology_and_cost_guardrails_are_bounded():
    topology = _read("01_databases_and_schemas.sql").upper()
    guardrails = _read("02a_compute_cost_guardrails.sql").upper()
    for schema in ("LANDING", "STAGING", "CORE", "MARTS"):
        assert f"SPOTIFY_ANALYTICS.{schema}" in topology
    assert "WAREHOUSE_SIZE = XSMALL" in topology
    assert "AUTO_SUSPEND = 60" in topology + guardrails
    assert "INITIALLY_SUSPENDED = TRUE" in topology
    assert "MAX_CLUSTER_COUNT = 1" in topology
    assert "SUSPEND_IMMEDIATE" in guardrails
    assert "STATEMENT_TIMEOUT_IN_SECONDS = 900" in guardrails
    assert "CREATE RESOURCE MONITOR IF NOT EXISTS SPOTIFY_DEV_MONITOR WITH" in guardrails
    assert "CREDIT_QUOTA = 2" in guardrails
    assert "FREQUENCY = MONTHLY" in guardrails


def test_rbac_contains_only_intended_service_roles_and_least_privilege_boundaries():
    sql = _read("02_rbac_roles_and_grants.sql").upper()
    for role in ("SPOTIFY_LOADER", "SPOTIFY_TRANSFORMER", "SPOTIFY_ANALYST"):
        assert f"CREATE ROLE IF NOT EXISTS {role}" in sql
    assert "GRANT ALL" not in sql
    assert "GRANT USAGE ON WAREHOUSE COMPUTE_WH TO ROLE SPOTIFY_LOADER" not in sql
    assert "SPOTIFY_ANALYTICS.MARTS TO ROLE SPOTIFY_ANALYST" in sql
    assert "SPOTIFY_ANALYTICS.LANDING TO ROLE SPOTIFY_ANALYST" not in sql


def test_storage_contract_uses_only_inert_placeholders_and_no_static_keys():
    executable_corpus = "\n".join(
        path.read_text(encoding="utf-8")
        for path in list(DDL.glob("*.sql")) + list((SNOWFLAKE / "validation").glob("*.sql"))
    )
    template_corpus = "\n".join(
        path.read_text(encoding="utf-8") for path in (SNOWFLAKE / "templates").glob("*.example")
    )
    corpus = executable_corpus + "\n" + template_corpus
    integration = _read("03_storage_integration.sql")
    assert "STORAGE_AWS_ROLE_ARN = '__AWS_ROLE_ARN__'" in integration
    assert "STORAGE_AWS_EXTERNAL_ID = '__AWS_EXTERNAL_ID__'" in integration
    assert "STORAGE_ALLOWED_LOCATIONS = ('s3://__S3_BUCKET__/silver/')" in integration
    assert "CREATE OR REPLACE STORAGE INTEGRATION" not in executable_corpus.upper()
    assert not re.search(r"arn:aws:iam::\d{12}:", corpus)
    for forbidden in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "PRIVATE_KEY"):
        assert forbidden not in corpus.upper()


def test_stage_file_format_and_five_pipes_match_silver_prefixes():
    stage = _read("04_external_stages.sql").upper()
    fmt = _read("05_file_formats.sql").upper()
    pipes = _read("07_snowpipes.sql")
    assert "DIRECTORY = (ENABLE = TRUE)" in stage
    assert "COMPRESSION = SNAPPY" in fmt
    assert "USE_LOGICAL_TYPE = TRUE" in fmt
    datasets = ("artists", "albums", "tracks", "track_artists", "playlist_snapshots")
    assert pipes.upper().count("CREATE PIPE IF NOT EXISTS") == 5
    assert pipes.upper().count("AUTO_INGEST = TRUE") == 5
    for dataset in datasets:
        assert f"SILVER_STAGE/{dataset}/" in pipes
    for metadata in ("METADATA$START_SCAN_TIME", "METADATA$FILENAME", "METADATA$FILE_ROW_NUMBER"):
        assert pipes.count(metadata) == 5
    assert "CURRENT_TIMESTAMP" not in pipes.upper()
    assert "ON_ERROR = ABORT_STATEMENT" not in pipes.upper()


def _table_columns(sql: str, table: str) -> list[str]:
    pattern = rf"CREATE TABLE IF NOT EXISTS SPOTIFY_ANALYTICS\.LANDING\.{table}\s*\((.*?)\);"
    match = re.search(pattern, sql, flags=re.IGNORECASE | re.DOTALL)
    assert match, f"missing table {table}"
    return [
        line.strip().split()[0].upper().rstrip(",")
        for line in match.group(1).splitlines()
        if line.strip()
    ]


def test_landing_columns_match_m3_silver_plus_audit_metadata():
    sql = _read("06_landing_tables.sql")
    audit = ["_LOADED_AT", "_FILE_NAME", "_FILE_ROW_NUMBER"]
    expected = {
        "LANDING_ARTISTS": ["ARTIST_ID", "ARTIST_NAME", "INGESTION_DATE"],
        "LANDING_ALBUMS": [
            "ALBUM_ID",
            "ALBUM_NAME",
            "ALBUM_TYPE",
            "RELEASE_DATE",
            "TOTAL_TRACKS",
            "INGESTION_DATE",
        ],
        "LANDING_TRACKS": [
            "TRACK_ID",
            "TRACK_NAME",
            "ALBUM_ID",
            "DURATION_MS",
            "IS_EXPLICIT",
            "IS_LOCAL",
            "INGESTION_DATE",
        ],
        "LANDING_TRACK_ARTISTS": ["TRACK_ID", "ARTIST_ID", "ARTIST_ORDER", "INGESTION_DATE"],
        "LANDING_PLAYLIST_SNAPSHOTS": [
            "PLAYLIST_ID",
            "SPOTIFY_SNAPSHOT_ID",
            "PLAYLIST_NAME",
            "TRACK_ID",
            "TRACK_POSITION",
            "ADDED_AT",
            "SNAPSHOT_DATE",
            "SNAPSHOT_TIMESTAMP",
            "PIPELINE_RUN_ID",
            "INGESTION_DATE",
        ],
    }
    for table, silver_columns in expected.items():
        assert _table_columns(sql, table) == silver_columns + audit


def test_validation_sql_covers_errors_rejections_latency_duplicates_and_partition_lineage():
    sql = (
        (SNOWFLAKE / "validation" / "verify_landing_loads.sql").read_text(encoding="utf-8").upper()
    )
    for token in (
        "COPY_HISTORY",
        "ERROR_COUNT",
        "REJECTED_ROWS",
        "LOAD_LATENCY_SECONDS",
        "HAVING COUNT(*) > 1",
        "INGESTION_DATE=",
        "PIPELINE_RUN_ID",
    ):
        assert token in sql
