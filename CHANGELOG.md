## 2025-09-13 00:00 UTC

- Add IBM DB2 11.5 Docker service in `docker-compose.yml`.
- Make `app/blocker.py` backend-agnostic (DB2 + PostgreSQL):
  - Declare index via SQLAlchemy; remove backend-specific `CREATE INDEX IF NOT EXISTS`.
  - Export `get_blocked_table()` and publish `blocked_table` after initialization.
- Update `app/api.py` to fetch the table via `get_blocked_table()` at runtime.
- Update backend tests to document valid DB2 URLs.
- Add DB2 drivers to `requirements.txt` (`ibm-db`, `ibm-db-sa`).

## 2025-09-13 00:20 UTC

- Compose: add `postfix_db2` service (SMTP 1026, API 5002) to run Postfix with DB2 alongside Postgres.
- Backend tests: parameterize to exercise both Postgres and DB2 in one pytest run by default; skip if unavailable.
- E2E tests: add `tests/test_e2e.py` to run a minimal end-to-end scenario against both backends in one run; no manual config needed.
- README: document dual Postfix services, E2E running, and default ports.

## 2025-09-13 00:40 UTC

- Testing best practices: added pytest markers (unit/backend/e2e) via `pytest.ini`.
- Added DB/SMPP readiness helpers in `tests/utils_wait.py` and integrated into backend and e2e tests to reduce initial skips.
- Added `tests/test_e2e.py` e2e test harness to exercise both backends in one run with readiness waits.
- CI: Added GitHub Actions workflow `.github/workflows/ci.yml` with separate unit, backend, and e2e jobs.

## 2025-09-13 11:45 UTC

- Docker: Split Python dependencies into `requirements-base.txt` and `requirements-db2.txt`.
- Dockerfile: Make DB2 dependencies optional via `ENABLE_DB2` build arg to avoid build failures on arm64.
- Compose: Set `platform: linux/amd64` for postfix services; enable DB2 deps only for `postfix_db2`.
- Docs: Update README about conditional DB2 deps and platform notes.
- Verified: Brought up `db`, `mailhog`, and `postfix` services and validated E2E demo for PostgreSQL.

## 2025-09-14 04:55 UTC

- Tests: Fix E2E to avoid SQLAlchemy connect_args incompatible with DB2; add optional debug logging.
- Backend: Adjust app/blocker.py to avoid duplicate index creation and DB2 warnings; simplify schema.
- Docker: Rebuild postfix images to include latest app code; confirmed DB2 stack works end-to-end.
- Local runs: Execute tests from host against exposed ports; no tests copied into DB containers.
