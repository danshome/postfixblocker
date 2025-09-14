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

When backend/e2e tests are selected, pytest can optionally run
`docker compose down` and `docker compose up --build -d` first. To force this
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

