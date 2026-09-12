# Snowflake & Snowpipe contracts (M4)

This directory contains **offline, version-controlled deployment contracts** for M4. None
of these statements are executed by CI or by the current coding round. Live account,
region, edition, S3, IAM, stage, and Snowpipe validation remains deliberately deferred.

## Execution order for the later cloud phase

1. `ddl/01_databases_and_schemas.sql`
2. `ddl/02_rbac_roles_and_grants.sql`
3. `ddl/02a_compute_cost_guardrails.sql`
4. replace the inert quoted placeholders in `ddl/03_storage_integration.sql`, then execute it
5. run `DESC INTEGRATION SPOTIFY_S3_INTEGRATION` and copy Snowflake's generated
   `STORAGE_AWS_IAM_USER_ARN` into the AWS trust relationship
6. deploy the trust relationship represented by `templates/aws_role_trust_policy.json.example`
   through M8 Terraform; never commit the real ARN/external ID
7. execute `ddl/05_file_formats.sql`, `ddl/04_external_stages.sql`, and
   `ddl/06_landing_tables.sql`
8. execute `ddl/07_snowpipes.sql` under the least-privileged loader role after its grants
9. configure S3 object-created notifications for the Snowflake-managed SQS notification
   channels in M8 Terraform
10. run the read-only checks in `validation/verify_landing_loads.sql`

Verify the actual Snowflake cloud/region before deployment. The architecture intends AWS
N. Virginia where possible, but this repository does not assert an unverified account
region.

## Security and idempotency

The storage integration is limited to `s3://__S3_BUCKET__/silver/` and uses cross-account
role assumption; there are no static AWS keys. `CREATE OR REPLACE STORAGE INTEGRATION` is
intentionally prohibited because recreating an integration can break existing stage
associations. Service-role SQL assigns no users and does not embed `ACCOUNTADMIN` or
`SYSADMIN` into application automation.

The DDL uses `IF NOT EXISTS` plus explicit `ALTER` statements where convergence is safe.
Snowpipe definitions are not blindly replaced because recreating a pipe changes its object
identity and requires a controlled pause/drain/recreate procedure. Future COPY definition
changes must follow that migration procedure rather than an unattended replace.

## Static SQL validation

CI uses SQLFluff 4.3.0 with the Snowflake dialect to parse all deployment and validation
SQL that its current grammar supports. Two current Snowflake clauses are explicitly listed
in `.sqlfluffignore`: the `CREATE RESOURCE MONITOR ... WITH ...` body and
`STORAGE_AWS_EXTERNAL_ID` in `CREATE STORAGE INTEGRATION`. SQLFluff 4.3.0 does not yet
recognize those clauses even though they are present in current Snowflake SQL reference
syntax. Dedicated Python contract tests pin their exact expected forms instead of deleting
or weakening valid Snowflake functionality merely to satisfy a lagging parser. They still
require live syntax verification in the later cloud phase before M4 is called deployed.

## Cost controls

`COMPUTE_WH` is X-Small (`XSMALL` in current Snowflake SQL), single-cluster,
auto-suspends after 60 seconds, starts suspended, and has bounded queue/statement timeouts.
`SPOTIFY_DEV_MONITOR` is a development safety fuse at 2 warehouse credits/month with an
80% notification and immediate suspension at 100%. This is not a dollar guarantee because
credit pricing varies by account/region and it does not meter serverless Snowpipe usage.

## Loading semantics

Each of the six Silver datasets has one pipe. `playlist_observations` carries one row per
physical playlist run even when zero valid tracks exist, so downstream analytics can
distinguish an observed empty playlist from a missing pipeline day. The COPY transformations cast Parquet fields explicitly
into Landing types and append `_loaded_at`, `_file_name`, and `_file_row_number` from
Snowflake metadata. `_loaded_at` uses `METADATA$START_SCAN_TIME`, not wall-clock SQL
functions. The file's `ingestion_date` remains data, and validation verifies that it agrees
with the Hive partition path.

M3 explicitly writes Spark `TimestampType` values as Parquet `TIMESTAMP_MICROS` rather than
the legacy INT96 default. Snowpipe still normalizes timestamp instants and
`METADATA$START_SCAN_TIME` to UTC before casting to Landing `TIMESTAMP_NTZ`. The later live
validation phase must prove this with a known UTC instant while the Snowflake session uses
a non-UTC timezone, so session settings cannot silently change lineage values.

Snowpipe's loaded-file tracking prevents routine file replay; it is **not** the analytical
business deduplication key. M5 dbt resolves retries at the canonical grain:
`playlist_id + snapshot_date + track_position`. `snapshot_timestamp` and
`pipeline_run_id` remain lineage/tie-break metadata and never enter that natural key.

## Source policy boundary

M4 is synthetic/offline-first. These contracts must not be interpreted as approval to
persist or analyze live Spotify-derived portfolio datasets. Checked-in fixtures remain
synthetic until permitted usage is established separately.
