## Description

Briefly explain the intent of this PR, the problem it solves, or the feature it introduces.

Closes #<!-- issue number -->

---

## Type of Change

Please mark the relevant option(s) with an `x`:

- [ ] `feat`: New feature or capability
- [ ] `fix`: Bug fix
- [ ] `docs`: Documentation updates or additions
- [ ] `test`: Unit, integration, or contract tests
- [ ] `infra`: Infrastructure as Code (Terraform) changes
- [ ] `data`: Schema or pipeline transformation changes
- [ ] `ci`: CI/CD pipeline or workflow changes
- [ ] `refactor`: Code restructuring without behavioral change

---

## Architectural Alignment

- [ ] Follows principles established in [docs/PROJECT_BLUEPRINT.md](docs/PROJECT_BLUEPRINT.md).
- [ ] Conforms to relevant Architectural Decision Records ([docs/adr/](docs/adr/)).
- [ ] Airflow remains strictly an orchestrator (no heavy processing in DAG definitions).
- [ ] PySpark handles technical schema extraction and Parquet serialization.
- [ ] dbt handles analytical modeling and warehouse transformations.
- [ ] Zero credentials or sensitive environment variables introduced.

---

## Testing & Verification

Describe the manual or automated tests executed to verify these changes:

- [ ] `make lint` passed
- [ ] `make format-check` passed
- [ ] `make test` passed
- [ ] Additional validation steps: <!-- specify if applicable -->

---

## Checklist

- [ ] Code follows conventional commit guidelines.
- [ ] Code comments and documentation are written in clear English.
- [ ] No temporary files or secrets committed.
