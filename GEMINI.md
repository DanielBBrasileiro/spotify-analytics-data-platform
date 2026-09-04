# Gemini CLI Development Guidelines

These instructions govern all Gemini CLI sessions operating on the `spotify-analytics-data-platform` repository. Every agent must strictly adhere to these rules.

---

## 1. Architectural Guardrails

- **Read the Blueprint First**: Always consult [`docs/PROJECT_BLUEPRINT.md`](docs/PROJECT_BLUEPRINT.md) before making architectural modifications or proposing changes to existing interfaces.
- **Airflow is strictly an Orchestrator**: Never embed heavy data extraction, PySpark transformations, or warehouse querying logic directly inside Airflow DAG files or custom Airflow task scripts. Airflow's sole responsibility is scheduling, external service invocation (Lambda, Glue, Snowflake, dbt), sensor checking, and triggering quality gates.
- **Spark vs. dbt Separation of Concerns**:
  - **AWS Glue / PySpark**: Semi-structured JSON ingestion, schema enforcement, unnesting/exploding arrays, technical deduplication, and writing partitioned Parquet datasets to S3 Silver.
  - **dbt Core**: In-warehouse dimensional modeling (facts, dimensions, bridge tables, marts) inside Snowflake, incremental models, and analytical data quality assertions.
- **No Unjustified Technologies**: Do not introduce additional frameworks (e.g., Kafka, Flink, Kubernetes, EMR, Databricks, Redis) without explicit justification, cost-benefit analysis, and an approved Architecture Decision Record (ADR).
- **Architecture Decision Records (ADRs)**: If introducing a significant architectural decision, document it in `docs/adr/` following the existing format (`Title`, `Status`, `Context`, `Decision`, `Alternatives Considered`, `Consequences`, `Risks`, `Review Conditions`).

---

## 2. Safety, Security & Cost Controls

- **Zero Secrets Policy**: Never commit credentials, tokens, passwords, private keys, Spotify client secrets, AWS access keys, or Snowflake passwords to any file in this repository. Placeholders belong in `.env.example` only.
- **Zero Accidental Cloud Spend**: Never execute commands that deploy live cloud infrastructure (such as `terraform apply`, AWS CLI create commands, or Snowflake DDL/DML on paid instances) unless explicitly requested and confirmed by the user. Keep operational cost within the $20/month portfolio budget ceiling.
- **Preserve Idempotency & Immutability**: Raw ingestion files in S3 Bronze (`bronze/spotify/...`) are append-only and immutable. Never implement overwrites of historical bronze partitions.

---

## 3. Workflow & Code Standards

- **Issue-First Development**: Work strictly on the designated GitHub issue. Do not perform unrelated refactoring, incidental cleanup, or out-of-scope feature creep.
- **Inspect Before Modifying**: Always read and analyze existing files before making edits.
- **Small, Reviewable Changes**: Favor small, cohesive commits and pull requests.
- **Language**: All code, documentation, comments, commit messages, PR descriptions, and issues must be written in English.
- **Test-Driven Rigor**: Every production code addition must be accompanied by corresponding unit or integration tests in `tests/`.
- **Pre-Commit Verification**: Run `make check` (or `make lint`, `make format-check`, `make test`) prior to committing. Never claim a command passed unless it actually ran and returned exit code 0.
- **Conventional Commits**: Format commit messages per conventional commit specifications (e.g., `feat: ...`, `fix: ...`, `docs: ...`, `test: ...`, `chore: ...`).

---

## 4. Session Completion Checklist

At the conclusion of each working session, provide a structured summary containing:
1. Changed and created files.
2. Explicit commands executed and verification results.
3. Key assumptions made during implementation.
4. Remaining risks or open questions.
