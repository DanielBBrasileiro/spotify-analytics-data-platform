# Utility Scripts

This directory contains developer automation, data generation, and local testing utilities.

---

## Architectural Responsibility

- **Local Mocking & Fixture Generation**: Scripts to generate synthetic Spotify JSON payloads matching API contracts for offline unit and PySpark testing.
- **Environment Bootstrapping**: Local environment setup and credential validation checks.
- **Teardown Automation**: Verification scripts ensuring zero remaining cloud resources post-demonstration.

---

## Planned Directory Structure

```
scripts/
├── generate_mock_spotify_data.py   # Synthesizes realistic playlist and track JSON for tests
├── validate_local_env.sh           # Checks Python, Docker, uv, and CLI dependencies
└── cost_audit.sh                   # Scans AWS account for running instances or dangling volumes
```
