# Contributing Guidelines

Thank you for contributing to the **Spotify Analytics Data Platform**. This repository targets production-oriented practices at portfolio scale for code quality, documentation, testing, and Git hygiene.

---

## 1. Issue-First Development

Every contribution must be tied to an existing GitHub issue. If an issue does not exist for the work you intend to do, open one first using the appropriate issue template (`bug_report.yml` or `feature_request.yml`) and link it to the relevant milestone.

---

## 2. Branching Strategy

- All development branches must branch off `main`.
- Branch naming must reflect the issue type and scope:
  - `feat/<short-description>` (e.g., `feat/spotify-api-client`, `feat/lambda-extractor`, `feat/glue-transformations`, `feat/snowflake-ingestion`, `feat/dbt-models`, `feat/airflow-orchestration`)
  - `fix/<short-description>` (e.g., `fix/api-pagination-offset`, `fix/glue-schema-nullable`)
  - `docs/<short-description>` (e.g., `docs/update-runbook`, `docs/data-model-diagram`)
  - `test/<short-description>` (e.g., `test/pyspark-unit-fixtures`)
  - `infra/<short-description>` (e.g., `infra/s3-lifecycle-rules`)

---

## 3. Commit Guidelines (Conventional Commits)

Commit messages must follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

```
<type>(<optional scope>): <description>

[optional body]

[optional footer(s)]
```

### Allowed Types
- `feat`: A new feature or pipeline capability
- `fix`: A bug fix
- `docs`: Documentation only changes
- `style`: Changes that do not affect the meaning of the code (formatting, white-space)
- `refactor`: Code change that neither fixes a bug nor adds a feature
- `perf`: Code change that improves performance
- `test`: Adding missing tests or correcting existing tests
- `build`: Changes that affect the build system or external dependencies
- `ci`: Changes to CI configuration files and scripts
- `chore`: Routine maintenance tasks

### Examples
- `feat: add Spotify API client`
- `feat: implement Lambda extractor`
- `test: add playlist parser tests`
- `docs: document data lake architecture`
- `ci: add Python quality checks`
- `fix: handle API pagination`
- `refactor: isolate S3 persistence layer`

---

## 4. Local Quality Assurance

Before pushing a branch or opening a pull request, run the test suite and static analysis suite:

```bash
make check
```

This runs:
1. `make lint`: Ruff static analysis (`ruff check .`)
2. `make format-check`: Ruff formatting validation (`ruff format --check .`)
3. `make test`: Unit tests with pytest (`pytest`)

All checks must pass with exit code 0.

---

## 5. Architectural Decision Records (ADRs)

If a pull request introduces an architectural shift (e.g., changing an ingestion engine, altering partition strategies, introducing a warehouse paradigm, or adding new cloud services), an Architecture Decision Record must be submitted in `docs/adr/`. Follow the format established in `docs/adr/0001-airflow-as-orchestrator.md`.

---

## 6. Pull Request Process

1. Open a pull request against the `main` branch.
2. Complete the checklist in `.github/pull_request_template.md`.
3. Ensure CI passes cleanly.
4. Keep PRs focused, atomic, and bounded to the referenced issue.
