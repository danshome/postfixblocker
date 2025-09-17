<!-- Updated to best practices on 2025-09-14. -->
# Testing

<!-- BEGIN GENERATED: TESTING:MAIN -->

This document outlines the testing strategy and how to run tests locally and
in CI.

## Strategy

- Unit: fast, isolated; aim for high coverage of pure logic
- Backend: exercises DB interactions for PostgreSQL and DB2
- E2E: full stack including Postfix and MailHog

Target coverage: TODO (e.g., 80% lines)

## Running Tests

```bash
{{TEST_CMD}}
```

Example for this repo:

```bash
pytest -q
pytest -m unit
pytest -m backend
pytest -m e2e
```

## Linting (Serverless)

This repo supports local, serverless static analysis (no SonarQube server required).

Python (ruff, mypy, bandit):

```
python -m pip install -r requirements-dev.txt
./scripts/lint-python.sh
```

Angular/TypeScript (ESLint + sonarjs):

```
cd frontend
npm install
npm run lint
```

Tooling configs:
- Ruff + Mypy in `pyproject.toml`
- Bandit in `.bandit`
- ESLint in `frontend/.eslintrc.cjs`

## Pre-commit hooks

Install and enable pre-commit to run the linters automatically on commit:

```
python -m pip install -r requirements-dev.txt
pre-commit install
# Run on all files once
pre-commit run --all-files
```

Hooks included:
- Ruff format + lint (Python)
- Mypy (types)
- Bandit (security)
- ESLint (frontend TypeScript)

When backend/e2e tests are selected, pytest can optionally run
`docker compose stop` and `docker compose up --build -d` first. To force this
for any run, use:

```bash
pytest --compose-rebuild
# or
PYTEST_COMPOSE_ALWAYS=1 pytest
```

## Writing Tests

- Place unit tests under `tests/` with `test_*.py` naming.
- Use fixtures for shared setup; avoid global state.
- Prefer deterministic tests; mark flaky tests and investigate promptly.

## CI Tips

- Split unit, backend, and e2e jobs for parallelism.
- Capture container logs on failure.

<!-- END GENERATED: TESTING:MAIN -->


## E2E Observability Note

The blocker service emits a deterministic single-line marker when it applies updated maps and (re)loads Postfix:

```
BLOCKER_APPLY maps_updated total_entries=N marker=... hash=...
```

E2E suites prefer this marker when waiting for a mode change to take effect. However, SMTP behavior is the source of truth: tests ultimately verify delivery (MailHog) or rejection (RCPT 5xx). This ensures we don’t hide real problems behind log timing—if enforcement didn’t apply, the SMTP check fails.
