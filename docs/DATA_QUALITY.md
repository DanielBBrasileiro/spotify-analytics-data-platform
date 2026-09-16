# Cross-Tier Data Quality Contract

Data quality in the Spotify Analytics Data Platform is enforced as a **sequence of fail-closed contracts**, not as one final test suite after the data has already propagated through every layer.

Each gate answers a different question:

- **Can the source-shaped payload be trusted enough to process?**
- **Did Spark produce technically valid curated datasets?**
- **Did Snowpipe load exactly the physical files Glue declared?**
- **Does the warehouse preserve the intended logical grain and relationships?**
- **Does the serving layer preserve the consumer contract?**

The complete offline contract suite is exposed through:

```bash
make check-quality
```

---

## 1. Quality Gates at a Glance

<!--
VISUAL ASSET 19
Target: docs/assets/quality/cross-tier-quality-gates.png
Prompt: docs/assets/README.md#19--cross-tier-data-quality-gates
When ready:
![Cross-Tier Data Quality Gates](assets/quality/cross-tier-quality-gates.png)
-->

```text
Source / Bronze
      │
      │ valid source shape + lineage
      ▼
Glue / Silver
      │
      │ explicit schemas + quarantine accounting
      ▼
Completion Manifest
      │
      │ exact physical file inventory
      ▼
Snowflake Landing
      │
      │ exact filenames + rows + row-number uniqueness
      ▼
dbt Staging / Core / Marts
      │
      │ grain + relationships + business rules
      ▼
BI_* Serving Views
      │
      │ row-key + coverage + semantic contracts
      ▼
Consumer refresh
```

No later gate is intended to compensate for a missing earlier one. A perfect dbt test suite cannot prove that Snowpipe loaded every physical file Glue expected unless the Landing boundary itself is reconciled.

---

## 2. Gate 1 — Source and Bronze Integrity

### Purpose

Reject malformed or inconsistent source-shaped payloads before expensive downstream work begins.

### Contracts

- required source metadata is validated before S3 publication;
- invalid snapshot metadata is rejected before the S3 client is invoked;
- source identifiers follow the platform's accepted contract;
- the CC0 adapter validates required CSV fields and positive duration values;
- pagination/source parsing contracts handle local items, non-track items, missing IDs and duplicate artist IDs explicitly;
- Bronze publication is run-scoped and immutable for a physical attempt;
- a retry is accepted only when the already-published object is byte-identical to the planned body.

### Failure behavior

Invalid source input fails before curation. A retry cannot silently replace the Bronze bytes for an existing physical `pipeline_run_id`.

---

## 3. Gate 2 — Spark / Silver Technical Validity

### Purpose

Convert semi-structured source payloads into typed relational datasets while making rejected source items explicit.

### Contracts

Glue 5.1 / Spark 3.5.6 uses explicit schemas for the curated datasets:

```text
artists
albums
tracks
track_artists
playlist_snapshots
playlist_observations
```

The Spark contract suite verifies, among other behavior:

- required/non-null Silver fields;
- track and artist identity handling;
- valid track extraction;
- positive/available duration behavior;
- deterministic deduplication;
- multi-artist billing order;
- playlist slot preservation;
- malformed Bronze rejection without echoing sensitive payloads;
- Parquet schema/layout compatibility;
- rejected-item classification and accounting.

### Quarantine semantics

Rejected playlist items are counted and classified rather than disappearing silently. `playlist_observations` preserves:

```text
source_item_count
valid_track_count
rejected_item_count
```

The bounded CC0 demo expects `rejected_item_count = 0`. A non-zero rejected count blocks the validated demo path at the Landing gate instead of being silently accepted as complete.

---

## 4. Gate 3 — Glue Completion Inventory

### Purpose

Create the authoritative physical contract between Spark output and warehouse readiness.

After successful curation, Glue publishes:

```text
metadata/curation/<pipeline_run_id>/complete.json
```

The manifest records:

- physical `pipeline_run_id`;
- logical snapshot date and playlist identity;
- rejected-item count;
- all six required datasets;
- exact Silver object keys;
- row counts per output file.

The completion document is itself validated for schema version, lineage, legal path boundaries, non-negative row counts, duplicate entries and required observation semantics.

No valid completion manifest means the downstream path has no authoritative claim of what should have loaded.

---

## 5. Gate 4 — Exact Snowflake Landing Readiness

### Purpose

Prove that Snowpipe loaded **the exact physical run output**, not merely that some data exists in Landing.

For every dataset, Airflow compares the completion inventory with Snowflake rows using file metadata.

The gate verifies:

- expected run-scoped filenames are present;
- no unrelated files satisfy the gate;
- row counts match the manifest;
- `_FILE_ROW_NUMBER` values are distinct as expected;
- duplicate physical rows are not accepted;
- excess rows do not count as success;
- positive-row files that have not arrived keep the sensor waiting;
- explicit zero-row datasets are handled as legitimate empty outputs.

This is stricter than checking a table-level count because the table can contain rows from several physical runs.

### Failure behavior

dbt is structurally downstream of every mapped `await_landing` task. If any physical snapshot cannot prove readiness, analytical transformation does not start.

---

## 6. Gate 5 — dbt Warehouse Integrity

### Purpose

Establish the logical analytical contract after physical ingestion is complete.

dbt tests cover:

- primary grain uniqueness;
- not-null keys;
- dimensional relationships;
- accepted values;
- source-item accounting rules;
- canonical playlist/date/position fact semantics;
- mart-level business invariants;
- idempotent model behavior;
- serving-view row keys and coverage.

The canonical fact grain is:

```text
(playlist_id, snapshot_date, track_position)
```

`pipeline_run_id` is preserved as lineage but excluded from that key, allowing physical replay to converge on the same logical fact.

---

## 7. Gate 6 — Serving Contract Validation

### Purpose

Protect the final analytical handoff from semantic drift that may not violate lower-level schemas.

The `BI_*` models validate:

- unique row keys at each published grain;
- required labels and IDs;
- accepted `NEW` / `RETAINED` / `EXITED` movement states;
- one-based position semantics in serving views;
- source/temporal provenance fields;
- row-count/coverage relationships between source marts and serving views.

The validated public surface is documented in [`SERVING_CONTRACT.md`](SERVING_CONTRACT.md).

---

## 8. Failure Evidence

Quality failures are not meant to disappear inside a generic “pipeline failed” status.

Depending on the boundary, evidence is available in:

- task logs;
- structured Airflow failure events;
- `plan.json`;
- `glue-<pipeline_run_id>.json`;
- Glue completion metadata when curation reached completion;
- `landing-<pipeline_run_id>.json`;
- dbt `run_results.json` and summary artifacts;
- `run-summary.json`;
- generated `pipeline-run-report.json`.

This lets an operator determine **which contract failed** before deciding whether replay is safe.

---

## 9. Quality and Replay

Replay is not used to bypass a failed quality gate.

The safe sequence is:

1. identify the failing boundary;
2. inspect its evidence;
3. determine whether the failure is source/data-related, delayed ingestion, external-service failure, or orchestration failure;
4. correct the underlying condition when required;
5. dry-run the replay command;
6. create a new physical attempt only when replay is appropriate;
7. require every quality gate to pass again.

Never clear and blindly rerun `curate.submit` to “fix” a quality failure. Glue submission is intentionally non-retryable because an ambiguous external response can duplicate physical work.

See [`RUNBOOK.md`](RUNBOOK.md).

---

## 10. Running the Cross-Tier Contract Suite

`make check-quality` intentionally composes multiple technology-specific test environments rather than pretending the entire platform has one runtime:

```text
orchestration contracts
        ↓
Airflow DAG/service contracts
        ↓
Spark / Glue-parity contracts
        ↓
dbt parse
        ↓
dbt project/data contracts
```

With the dedicated environments prepared:

```bash
export JAVA_HOME=/path/to/java-17
make check-quality
```

The command is designed as an offline/contract validation path. Live cloud runs remain separate, explicit and bounded.

---

## 11. Validated v1.0.0 Evidence

For the bounded cloud slice:

- three logical snapshot dates passed the physical and analytical gates end to end;
- the dbt build completed **152/152** nodes/tests successfully;
- a one-date replay completed the same **152/152** build;
- the replayed date remained **12 rows / 12 unique fact grains**;
- total fact count remained **36**;
- all four `BI_*` views were queryable with `SPOTIFY_ANALYST`.

The demo source has deterministic synthetic temporal evolution. These quality results prove the pipeline contracts for that bounded slice; they do not convert the synthetic changes into real Spotify history.
