# Interview Guide: Spotify Analytics Data Platform

Use this guide to explain the engineering decisions in the repository without overstating the validation boundary.

For a timed walkthrough, see [`DEMO_GUIDE.md`](DEMO_GUIDE.md).

---

## 1. 60-Second Project Summary

The project is a low-cost batch analytics platform for playlist snapshots. Source payloads land
immutably in S3 Bronze, Glue 5.1 performs technical normalization into six Silver Parquet
datasets, Snowpipe loads a Snowflake Landing layer, dbt owns the business/star model, and
Airflow 3 orchestrates the boundaries with retries, sensors, quality gates, Deadline Alerts,
and per-run evidence.

The public portfolio demo uses CC0-licensed Spotify-like catalog metadata and a clearly marked
synthetic three-day playlist history. That allows the AWS/Snowflake/dbt architecture to be
demonstrated without claiming that the demo history was observed from Spotify. Live Spotify
Lambda extraction exists as a separately tested source contract and should not be presented as
end-to-end validated unless a real source-side run has been captured.

---

## 2. Spotify Web API Constraints in 2026

The source design reflects the current Spotify Web API rather than older tutorial assumptions.
As checked against Spotify's documentation in September 2026:

- Long-running server-side access uses Authorization Code Flow and can refresh access tokens.
- Access tokens expire after one hour. Developer Dashboard refresh tokens have a six-month
  lifetime, after which operator reauthorization is required.
- Development Mode currently allows up to five authenticated allowlisted Spotify users, and
  the app owner must have Spotify Premium.
- Development Mode quota is shared across apps under the developer account; quota exhaustion
  is distinguishable from ordinary rate limiting through the 429 response reason.
- `GET /v1/playlists/{playlist_id}/items` is paginated and accepts at most `limit=50` per
  request. The API may return item types beyond tracks, so the pipeline validates item `type`
  instead of assuming every playlist entry is a track.

Useful primary references:

- Spotify Authorization Code Flow: <https://developer.spotify.com/documentation/web-api/tutorials/code-flow>
- Spotify refreshing tokens: <https://developer.spotify.com/documentation/web-api/tutorials/refreshing-tokens>
- Spotify playlist items endpoint: <https://developer.spotify.com/documentation/web-api/reference/get-playlists-items>
- Spotify quota modes: <https://developer.spotify.com/documentation/web-api/concepts/quota-modes>

The extractor captures playlist metadata `snapshot_id` separately from paginated `/items`
responses. It checks the source version around pagination so pages from two playlist versions
are not silently combined. A version change aborts the attempt and a new physical run can fetch
the new atomic snapshot.

---

## 3. `spotify_snapshot_id` vs `pipeline_run_id`

| Identifier | Question answered |
| --- | --- |
| `spotify_snapshot_id` | Which upstream playlist version did this observation represent? |
| `pipeline_run_id` | Which physical execution produced these Bronze/Silver/Landing artifacts? |

`spotify_snapshot_id` belongs to source semantics. `pipeline_run_id` belongs to execution
lineage. Reusing one as the other would make replays ambiguous: the same logical source version
can be processed more than once, and one execution can fail before a source snapshot ID is even
known.

In the CC0 demo, the source-version field is deliberately namespaced/simulated and the report
also carries `source_type=cc0_demo` and `temporal_state=synthetic` so it cannot be mistaken for
observed Spotify history.

---

## 4. Canonical Fact Grain

The canonical playlist fact is one occupied playlist slot on one logical observation date:

```text
(playlist_id, snapshot_date, track_position)
```

dbt derives `snapshot_pk` from that business grain. Physical timestamps, Glue job IDs, and
`pipeline_run_id` remain lineage attributes rather than becoming part of the analytical key.
This lets corrected replays converge on the same analytical rows while preserving separate
physical evidence.

Track position is part of the grain rather than only `track_id` because one playlist can
contain the same track in more than one slot.

---

## 5. Idempotent Reruns and Backfills

Within one Airflow run, the planned `pipeline_run_id` stays stable across task retries. Bronze
publication is conditional/immutable, Glue writes to run-scoped Silver prefixes, and completion
metadata inventories the exact files. An ambiguous Glue submit is not blindly retried.

A new replay creates a fresh physical run ID and therefore new immutable files, while dbt merges
on the canonical fact key. Replaying one logical date does not require deleting historical S3
objects.

```bash
.venv/bin/python scripts/replay_partition.py --date 2026-09-10 --dry-run
```

Only `--execute` triggers the DAG. A useful interview line is: “I separated immutable physical
history from logical model convergence, so reruns keep forensic lineage without duplicating the
business fact.”

---

## 6. Why Glue 5.1 and dbt Both Exist

| Glue 5.1 / Spark | dbt / Snowflake |
| --- | --- |
| Reads semi-structured Bronze JSON. | Starts after exact Landing readiness. |
| Enforces the technical source schema. | Applies warehouse-native business semantics. |
| Validates item types and quarantines malformed/unsupported entries. | Builds staging, dimensions, bridge, canonical fact, marts, and serving views. |
| Explodes arrays such as track artists. | Implements incremental merge keys and referential/data tests. |
| Produces six typed Parquet datasets plus a completion manifest. | Produces analytical models for consumers. |

The division keeps Spark focused on technical curation and dbt focused on analytical semantics.

---

## 7. Cross-Tier Quality Gate

Glue success alone is insufficient evidence that the warehouse is ready. The Glue completion
manifest declares all six expected Silver datasets and per-file row counts. Airflow then checks
Snowflake Landing against exact run-scoped filenames, total rows, and distinct file-row numbers.

The datasets are `artists`, `albums`, `tracks`, `track_artists`, `playlist_snapshots`, and
`playlist_observations`. Unexpected files, duplicates, partial positive-row files, or rejected
demo items prevent dbt from running. dbt then supplies business-layer tests after Landing
readiness.

---

## 8. Airflow 3 Task SDK and Deadline Alerts

The DAG uses `@dag`, `@task`, and `@task.sensor`, reschedule-mode sensors, exponential retry
backoff for transient tasks, and no retry on Glue submission because an ambiguous external
submit can create duplicate physical work. A `DeadlineAlert` is referenced to
`DAGRUN_QUEUED_AT` with a two-hour interval, and structured `DAG_FAILED` /
`DAG_DEADLINE_MISSED` callbacks emit safe context.

Airflow 3 removed the old SLA mechanism, so this project does not use legacy `sla=` arguments.

---

## 9. Unified Run Evidence

`scripts/generate_run_report.py` creates one schema-versioned `pipeline-run-report.json` from
Airflow plan/run status, Glue lineage/completion inventories, exact Landing readiness, rejected
item counts, source input count, per-dataset curated/loaded counts, and dbt elapsed time/node
count.

The report can remain local or be uploaded immutably under
`metadata/pipeline_runs/<run_key>.json`. In a `cc0_demo` report, `records_extracted` is the item
count in the generated Bronze payload, not proof of live Lambda extraction. A live Lambda run
uses its separate structured source events as the source-side evidence.

---

## 10. Cost Controls and Infrastructure Choices

The portfolio target is at most **$20/month**, treated as an operating target rather than a
guaranteed provider-side hard stop. The design controls cost structurally:

- Airflow runs locally in Docker instead of AWS MWAA.
- Lambda is outside a VPC, avoiding a NAT Gateway requirement.
- Glue is on-demand with a low worker count and bounded timeout.
- Snowflake uses an X-Small warehouse with aggressive auto-suspend and a resource monitor.
- Terraform defines one S3 lake bucket with `bronze/`, `silver/`, `artifacts/`, and `metadata/`
  prefixes, least-privilege IAM, the Lambda/Glue shapes, seven-day CloudWatch retention, and an
  AWS Budget variable defaulting to $20/month.

Infrastructure code proves the intended reproducible shape; HCL alone is not evidence that
every resource is currently deployed. For live spend statements, use measured evidence from
`docs/COST_STRATEGY.md`.

---

## 11. CC0 Source and Synthetic Temporal Boundary

The public demo separates two facts. Catalog-style source rows come from the CC0-licensed
`jeremycte/spotify-10000-songs-dataset` adaptation, while the three-day playlist evolution is
generated by this repository and marked `temporal_state=synthetic`.

The demo can support statements such as “the pipeline computes changes across three simulated
snapshots.” It does not support statements such as “Spotify observed these additions/exits on
those dates” or “these are real listening/popularity trends.” Provenance is carried into the
serving layer so future consumers can distinguish CC0/synthetic data from a separately
validated live source.

---

## 12. Serving Layer and BI Boundary

The repository defines four Snowflake serving views:

| View | Grain |
| --- | --- |
| `BI_PLAYLIST_DAILY` | playlist + snapshot date |
| `BI_TRACK_DAILY` | playlist + track + snapshot date |
| `BI_TRACK_CHANGES` | playlist + track + snapshot date/change state |
| `BI_ARTIST_DAILY` | artist + snapshot date |

`docs/SERVING_CONTRACT.md` defines their units, null semantics, one-based display positions,
provenance, and relationship guidance. The intent is to keep dashboard tooling thin and move
analytical semantics into versioned dbt models/views.

Do not claim a Power BI dashboard was validated unless that connection and dashboard have been
run separately. A documented, queryable serving contract is still a complete data-engineering
deliverable even when the visualization client is outside the validated slice.

---

## 13. Questions to Be Ready For

### Why not overwrite a failed partition?

Overwriting destroys forensic evidence and can race with asynchronous Snowpipe loading. Fresh
physical run IDs keep attempts immutable while dbt handles logical convergence.

### Why not put `pipeline_run_id` in the fact primary key?

It represents execution lineage rather than the business event. Including it would turn every
replay into a new analytical fact.

### Why not rely only on dbt tests?

dbt starts after Landing. The exact-file Landing gate catches incomplete or duplicate physical
loads first; dbt then validates model semantics and relationships.

### Why is the Glue submit task not retried?

An external submit can succeed even if the client times out before receiving the run ID. A
blind retry could create two jobs against one physical prefix, so the pipeline records a
submission claim and uses a fresh DAG run for recovery when needed.

### Why not use live Spotify data for the public demo?

Portfolio reproducibility should not depend on one developer account's current quota/auth
state. The CC0 source makes the demo repeatable, and the synthetic-temporal label prevents
provenance inflation.

### What would change for a larger production deployment?

Orchestrator hosting, alert routing, managed metrics/traces, storage format choices, and secret
rotation would become explicit scale/SLO decisions. Those are extension points, not claims
about the current portfolio slice.
