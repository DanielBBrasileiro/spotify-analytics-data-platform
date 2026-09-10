# Operational Runbook

## 1. Current operating boundary

M1 implements local authentication, extraction, fixtures/parsing, validated run
metadata, and immutable local Bronze persistence. Lambda, S3 API integration, Glue,
Snowflake, dbt, Airflow, Secrets Manager adapters, and recovery scripts are not
implemented/deployed.
Cloud procedures below are future runbook specifications, not executable setup.
Analytical demos use synthetic data under
[ADR-0008](adr/0008-synthetic-analytics-and-source-use-boundary.md).

## 2. Implemented local failure handling

| Symptom | Implemented behavior | Operator/caller action |
| --- | --- | --- |
| `InvalidGrantException` | Clears rejected refresh/access tokens and prevents further exchanges | Obtain new consent outside the library; supply new credentials securely and create a new client |
| `SnapshotChangedException` | Rejects the observation without returning a partial document | Restart the full extraction if the intended integration use is permitted |
| `RateLimitExceededException` | Stops after the request retry/wait budget | Inspect cadence and throttling; do not immediately loop on the failed call |
| `PaginationException` | Rejects contradictory pagination metadata | Inspect sanitized metadata and contract changes before retrying |
| HTTP 401/403 or transport failure | Raises `SpotifyExtractionException`; no automatic retry | Verify credentials, owner/collaborator access, and connectivity as applicable |
| Local Bronze collision | Raises `LocalBronzePersistenceError` and preserves the existing object | Treat the run directory as immutable; use a new UUID v4 for a new physical execution |

The extractor obtains `snapshot_id` from playlist metadata before pagination and
after every page, including the last. `/items` pages do not contain that version.
Checks detect observed changes; they do not create an atomic transaction or pin
a historical version. No automatic whole-extraction restart is implemented.

Refresh tokens expire six months after authorization; access-token refresh does
not extend the grant. Reauthorization is also required after revocation or other
`invalid_grant` failures. Rotation is in-memory only. No local consent utility,
expiry reminder, or secure persistence adapter exists yet. See
[ADR-0007](adr/0007-spotify-authorization-code-and-refresh-token.md) and the
[official refresh guide](https://developer.spotify.com/documentation/web-api/tutorials/refreshing-tokens).

Never put tokens in logs, chat, command-line arguments, or committed examples.
The client reads process environment or an injected mapping; copying `.env.example`
does not load `.env` automatically. Offline tests require no credentials.

Successful local snapshots are written under
`data/bronze/spotify/playlist_tracks/ingestion_date=YYYY-MM-DD/run_id=<uuid>/`.
The partition date comes from the UTC capture timestamp, while `snapshot_date`
remains the logical business date. The local writer uses no-clobber publication and
does not inject telemetry into the source snapshot JSON.

## 3. Planned cloud recovery

After the corresponding milestones implement and validate these components:

- **Lambda / Secrets Manager (M2):** expose sanitized domain errors and correlate
  runs. Reauthorization must securely update the secret through the future adapter;
  its write permissions and rotation behavior need explicit review.
- **Glue (M3):** inspect failed jobs and schema/quarantine counts. Replay retained
  synthetic Bronze partitions in the separate Glue 5.1 / Python 3.11 environment.
  Pass an actual UUID v4 as `pipeline_run_id`, not an arbitrary label.
- **Snowpipe (M4):** inspect pipe status, load errors, and file-level history before
  replay. File tracking does not replace business deduplication. Do not assume
  overwriting an already-loaded object automatically triggers a fresh load.
- **dbt (M5):** inspect failing compiled assertions, repair the relevant transform,
  and validate the selected dates. Define how canonical snapshots are selected
  and how obsolete slots are removed before relying on repeated merge runs.
- **Airflow (M6):** pin exact runtime/provider versions and validate recovery
  commands against those pins. Deadline Alerts require at least Airflow 3.1.

## 4. Planned historical replay and Airflow backfill

Replay requires existing raw observations for the requested dates. A current API
response cannot reconstruct an unobserved historical date. Physical replay time
and execution UUID must remain distinct from the original business observation.
Use the synthetic demonstration corpus for portfolio reprocessing.

The following is an **Airflow 3.1.0 reference example**, verified against its
[CLI documentation](https://airflow.apache.org/docs/apache-airflow/3.1.0/cli-and-env-variables-ref.html#backfill).
It has not been executed here. The DAG and its replay configuration do not exist
yet; M6 must implement a Bronze replay path that does not fetch current API state
for old logical dates. Recheck syntax when pinning the actual Airflow version.

```bash
airflow backfill create \
    --dag-id spotify_backfill_dag \
    --from-date YYYY-MM-DD \
    --to-date YYYY-MM-DD \
    --reprocess-behavior failed \
    --dry-run
```

`failed` selects reprocessing of failed runs; replacing completed observations
requires a deliberate policy and separate validation. A dry run is not evidence
that Glue, Snowpipe, or warehouse replay works. Once implemented, validate raw
availability, curated publication, Landing loads, canonical fact contents, and dbt
assertions before declaring a replay successful.

## 5. Local verification available today

```bash
make setup
make check
```

These commands exercise Ruff and offline pytest with coverage on Python 3.12.
They do not deploy resources, run Airflow, or validate live API access.
