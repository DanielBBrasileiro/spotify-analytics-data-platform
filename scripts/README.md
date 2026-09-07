# Utility Scripts

This directory currently contains only this design README. Data generators, environment validators, consent/recovery utilities, and cost-audit scripts have not been implemented.

Analytical demonstrations use fully synthetic data under [ADR-0008](../docs/adr/0008-synthetic-analytics-and-source-use-boundary.md).
The responsibilities and directory structure below are targets, not current implementation.

---

## Planned Architectural Responsibility

- **Local Mocking & Fixture Generation**: Scripts to generate synthetic Spotify JSON payloads matching API contracts for offline unit and PySpark testing.
- **Environment Bootstrapping**: Local environment setup and credential validation checks.
- **Teardown Automation**: Planned checks for managed resources, retained storage, and residual billing after demonstrations.

---

## Planned Directory Structure

```
scripts/
├── generate_mock_spotify_data.py   # Synthesizes realistic playlist and track JSON for tests
├── validate_local_env.sh           # Checks Python, Docker, uv, and CLI dependencies
└── cost_audit.sh                   # Scans AWS account for running instances or dangling volumes
```
