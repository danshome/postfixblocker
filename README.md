<!-- Updated to best practices on 2025-09-14; preserves project-specific content. -->
# Postfix Blocker

<!-- BEGIN GENERATED: README:STANDARD_BLOCK -->

[![CI Status](https://github.com/danshome/postfixblocker/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/danshome/postfixblocker/actions/workflows/ci.yml) [![Coverage](https://img.shields.io/badge/coverage-N%2FA-lightgrey.svg)](https://github.com/danshome/postfixblocker/actions)

This repository is owned by danshome and the canonical project name is
postfix-blocker (PyPI package; GitHub repo: postfixblocker). The primary
language is Python and the minimum supported toolchain is: Python 3.9+ and
Node.js 18+ (for the Angular frontend).

## At‑a‑Glance

- Key features:
  - API + background service to manage a Postfix recipient blocklist.
  - Supports PostgreSQL and IBM DB2 11.5 via SQLAlchemy.
  - Angular web UI for CRUD operations over `/addresses`.
  - Docker Compose for local development and E2E testing.

## Quickstart

Prerequisites: Python 3.9+, Node.js 18+, Docker (optional for full stack)

```bash
# Build, lint, and run tests for backend + frontend
make ci

# Run Python tests only
make test

# Start the full stack locally
docker compose up --build -d
```

Example for this repository:

```bash
# Unified build + tests (Python + frontend)
make ci

# Build + start services
docker compose up --build -d

# Run tests
pytest -q

# Tail API logs
docker compose logs -f postfix
```

## Contents

- [Quickstart](#quickstart)
- [Usage Examples](#usage-examples)
- [Project Structure](#project-structure)
- [Docs & Guides](#docs--guides)
- [License](#license)

## Usage Examples

List addresses via API:

```bash
curl -s http://localhost:5001/addresses | jq .
```

Add and delete an address:

```bash
curl -X POST http://localhost:5001/addresses \
  -H 'Content-Type: application/json' \
  -d '{"pattern":"user@example.com","is_regex":false, "test_mode":true}'

curl -X DELETE http://localhost:5001/addresses/1
```

## Project Structure

```text
postfix_blocker/  # Flask API and blocker service (Python package)
frontend/         # Angular web UI
docker/           # Container configuration
tests/            # Unit, backend, and E2E tests
```

## Docs & Guides

- [CONTRIBUTING](CONTRIBUTING.md)
- [CODE OF CONDUCT](CODE_OF_CONDUCT.md)
- [SECURITY](SECURITY.md)
- [CHANGELOG](CHANGELOG.md)
- [ROADMAP](ROADMAP.md)
- [ARCHITECTURE](ARCHITECTURE.md)
- [TESTING](TESTING.md)
- [SUPPORT](SUPPORT.md)
- [FAQ](FAQ.md)

## License

SPDX-License-Identifier: MIT. See [LICENSE](LICENSE) for details.

<!-- END GENERATED: README:STANDARD_BLOCK -->

<!--
Git hygiene (maintainers):
Suggested commit message for this sweep:
  docs: create/update repo standard docs (README, CONTRIBUTING, SECURITY, etc.)

If LICENSE changes are required, open a separate PR explaining rationale.
-->

This project provides a Python service and Angular web UI for managing a block
list of email recipients for Postfix. Blocked addresses are stored in a
database and automatically applied to Postfix, preventing delivery to those
recipients.

AGENTS.md contains development instructions for AI agents.

The service uses SQLAlchemy and supports PostgreSQL and IBM DB2 11.5.
For DB2 support, Python dependencies `ibm-db` and `ibm-db-sa` are required
(already listed in `requirements.txt`).

## Components

* **Python service (`postfix_blocker/blocker.py`)** – Monitors the database table and
  rewrites Postfix access maps when changes occur. Inside the Docker container
  the code lives under `/opt/postfix_blocker` and runs as a module
  (`python -m postfix_blocker.blocker`).
* **Flask API (`postfix_blocker/api.py`)** – REST API used by the Angular UI to manage
  blocked addresses.
* **Angular UI (`frontend`)** – Simple interface to view, add, and remove
  entries.
* **Docker Compose environment** – Includes Postfix, PostgreSQL, IBM DB2 (optional),
  and MailHog for local testing.

### API ↔ Blocker IPC (Refresh)

- Mechanism: signal-based IPC on the same host/container.
  - The blocker writes its PID to `BLOCKER_PID_FILE` (default: `/var/run/postfix-blocker/blocker.pid`).
  - After add/update/delete commits, the API reads the PID file and sends `SIGUSR1` to trigger an immediate refresh (rewrite maps → `postmap` → `postfix reload`).
- Configuration (already wired in Docker):
  - `BLOCKER_PID_FILE` for both processes (supervisord passes it through).
- Fallback behavior: if signaling fails (missing PID file, permissions, etc.), the blocker still detects changes via a lightweight DB marker (`max(updated_at)`, `count(*)`) within `BLOCKER_INTERVAL` seconds.
- Verify manually (inside the postfix container):
  - `kill -USR1 $(cat /var/run/postfix-blocker/blocker.pid)`
  - Tail logs for: “Preparing Postfix maps…”, “Running postmap…”, “Reloading postfix”.

## Running locally

```bash
docker compose up --build
```

The API is available on [http://localhost:5001](http://localhost:5001) and
MailHog's UI on [http://localhost:8025](http://localhost:8025).

PostgreSQL listens on port `5433` on the host to avoid conflicts with any
local installations. IBM DB2 listens on port `50000` if you enable the `db2`
service. Two Postfix services are available:

- `postfix` (PostgreSQL) – SMTP on host `1025`, API on `5001`
- `postfix_db2` (DB2) – SMTP on host `1026`, API on `5002`

Note: The Docker image for `postfix` installs only the base Python
dependencies (no DB2 client). The heavier DB2 client packages are installed
only in the `postfix_db2` image to keep builds fast and compatible across
architectures (e.g., Apple Silicon). Images are now based on Rocky Linux 9
to align with RHEL 9.5. The compose file pins services to `linux/amd64` for
reliable DB2 support.

Base image choice
- We use `rockylinux/rockylinux:9` (OSS‑sponsored, upstream‑maintained) rather
  than the deprecated `rockylinux:9` library image to ensure timely updates and
  security fixes.

### Database backends

- PostgreSQL (default):
  - Service: `db` (postgres:16)
  - Default URL: `postgresql://blocker:blocker@localhost:5433/blocker`
- IBM DB2 11.5 (optional):
  - Service: `db2` (ibmcom/db2:11.5.7.0)
  - Accepts license via `LICENSE=accept` env
  - Default credentials in compose: user `db2inst1`, db `BLOCKER`, password `blockerpass`
  - URL examples:
    - `ibm_db_sa://db2inst1:blockerpass@localhost:50000/BLOCKER`
    - `db2+ibm_db://db2inst1:blockerpass@localhost:50000/BLOCKER`
  - Note: DB2 container typically requires several GB of RAM and runs in
    privileged mode in the sample compose for simplicity in dev.
  - Architecture note: DB2 Python drivers are installed only on x86_64. On
    arm64 (e.g., Apple Silicon) local builds may skip driver install and DB2
    tests will be skipped.

Switching the Postfix service to DB2:

- Either use the `postfix_db2` service, or edit `docker-compose.yml` and change
  `BLOCKER_DB_URL` in the `postfix` service to the DB2 URL, e.g.:

```
BLOCKER_DB_URL=ibm_db_sa://db2inst1:blockerpass@db2:50000/BLOCKER
```

Then rebuild/restart:

```
docker compose up --build
```

## Postfix test mode (monitor-only)

This project supports a per-entry "test mode". When enabled for an address or
regex, mail to that recipient is not blocked; instead Postfix logs a warning
that the message would have been rejected. This uses `warn_if_reject` in
`smtpd_recipient_restrictions` with dedicated test access maps.

- Enforced maps: `/etc/postfix/blocked_recipients`, `/etc/postfix/blocked_recipients.pcre`
- Test maps: `/etc/postfix/blocked_recipients_test`, `/etc/postfix/blocked_recipients_test.pcre`

Rebuild and restart the Postfix containers after pulling this change so the
updated `main.cf` is applied:

```
docker compose build postfix postfix_db2
docker compose up -d
```

In the UI you can toggle mode per row, for selected rows, or set all
to Test/Enforce. New entries default to Test mode.

## Testing

Run unit tests:

```bash
pytest
```

Markers to scope runs:

- Unit: `pytest -m unit`
- Backend (requires Docker DBs): `pytest -m backend`
- E2E (requires full stack): `pytest -m e2e`

### Frontend testing (Angular 20)

Angular UI unit tests (Karma + Jasmine):

```
cd frontend
npm install
npm test  # runs ng test
```

Angular UI e2e tests (Playwright):

Prerequisites:
- Backend stack running: `docker compose up --build`

Run with Playwright starting the dev server and proxying API calls to the Flask API:

```
cd frontend
npm run e2e  # runs both Postgres and DB2 matrix sequentially (starts dev servers on 4200 then 4201)
```

Notes:
- Default Postgres API: `ng serve` uses `frontend/proxy.conf.json` to proxy `/addresses` to `http://localhost:5001`.
- DB2 API: use `npm run start:db2` which uses `frontend/proxy.db2.json` to proxy to `http://localhost:5002`.
- DB2 container can take a few minutes to initialize. If you see proxy ECONNRESET errors, wait until `curl http://localhost:5002/addresses` returns `[]` and refresh.
 - Ensure ports `4200` and `4201` are free before running the matrix.

Run e2e against DB2 only (optional):

```
cd frontend
npm run e2e:db2
```

This runs only the DB2 Playwright project. The test runner starts both dev servers via the matrix web server, then targets the DB2 UI (port 4201) and API (port 5002).

### Frontend DevContainers

Two DevContainer options are provided:

- Root UI DevContainer (auto-starts UI)
  - Open the repository root in VS Code → Reopen in Container.
  - Container auto-installs `frontend` deps and starts `ng serve` with proxy to the host API.
  - A status check waits for `http://localhost:4200` before marking the container ready.
  - Visit `http://localhost:4200`.
  - Image: `mcr.microsoft.com/playwright:v1.48.0-jammy` (Node + browsers).

- Frontend-only DevContainer
  - Open only the `frontend/` folder in VS Code → Reopen in Container.
  - Manually start the dev server: `npm run start:devc`.

Inside either container:

```
# Unit tests (Jest)
cd frontend && npm test

# E2E tests (Playwright)
cd frontend && npm run e2e
```

Notes:
- Both devcontainers forward `4200`.
- The dev server proxies `/addresses` to the host API (default `http://localhost:5001`). Ensure `docker compose up` is running.

PCRE map support
- PCRE map support is required to enforce regex rules. On RHEL/Rocky 9 it may
  be provided by the `postfix-pcre` subpackage; the image enables CRB and
  installs `postfix-pcre`, then asserts availability by checking that
  `postconf -m` contains `pcre` during build.

## End-to-end demo

The `tests/e2e_test.py` script demonstrates blocking behaviour by sending
emails through Postfix and verifying delivery via MailHog.

Prerequisites:
- Docker stack running: `docker compose up --build`
- Postfix exposes SMTP on host `localhost:1025`

Run from the repository root so the `app` package can be imported:

```bash
python tests/e2e_test.py
```

Configuration via environment variables (optional):
- `BLOCKER_DB_URL` (default `postgresql://blocker:blocker@localhost:5433/blocker`)
- `SMTP_HOST`/`SMTP_PORT` (defaults `localhost`/`1025`)
- `MAILHOG_HOST`/`MAILHOG_PORT` (defaults `localhost`/`8025`)

Running inside the Postfix container (useful on some hosts):

```bash
docker compose cp tests/e2e_test.py postfix:/opt/postfix_blocker/e2e_run.py
docker compose exec postfix env \
  BLOCKER_DB_URL=postgresql://blocker:blocker@db:5432/blocker \
  SMTP_HOST=127.0.0.1 SMTP_PORT=25 \
  MAILHOG_HOST=mailhog MAILHOG_PORT=8025 \
  python /opt/postfix_blocker/e2e_run.py
```

Mass traffic demo
- Simulate hundreds of emails (allowed + blocked), and block an allowed address mid-stream to prove the live blocker works:

```bash
# From host
python tests/e2e_test.py --mass --total 300

# Inside the postfix container (recommended if host DB port is blocked)
docker compose cp tests/e2e_test.py postfix:/opt/postfix_blocker/e2e_run.py
docker compose exec postfix env \
  BLOCKER_DB_URL=postgresql://blocker:blocker@db:5432/blocker \
  SMTP_HOST=127.0.0.1 SMTP_PORT=25 \
  MAILHOG_HOST=mailhog MAILHOG_PORT=8025 \
  python /opt/postfix_blocker/e2e_run.py --mass --total 300

Using DB2 instead of Postgres inside the postfix container:

```
docker compose exec postfix env \
  BLOCKER_DB_URL=ibm_db_sa://db2inst1:blockerpass@db2:50000/BLOCKER \
  SMTP_HOST=127.0.0.1 SMTP_PORT=25 \
  MAILHOG_HOST=mailhog MAILHOG_PORT=8025 \
  python /opt/postfix_blocker/e2e_run.py
```
```

Troubleshooting Postfix SMTP:
- Ensure PCRE map support is installed in the image (we install `postfix-pcre`).
- Disable smtpd chroot in containers: set `smtp/inet/chroot = n` (done in Dockerfile).
- Verify SMTP is listening: `docker compose exec postfix nc -vz 127.0.0.1 25`.
- The dev image allows relaying from the host by setting `mynetworks = 0.0.0.0/0` for convenience. Do NOT use this setting in production; restrict `mynetworks` appropriately.

The script populates the database with a couple of blocked addresses, sends
three messages, and prints which recipients were actually delivered to
MailHog (only the allowed recipient should arrive).

## Backend tests

Optional backend-specific smoke tests can be run by setting environment variables:

```
# PostgreSQL backend test
TEST_PG_URL=postgresql://blocker:blocker@localhost:5433/blocker pytest -q tests/test_db_backends.py

# IBM DB2 backend test
TEST_DB2_URL=ibm_db_sa://db2inst1:blockerpass@localhost:50000/BLOCKER pytest -q tests/test_db_backends.py
```

## E2E tests

Pytest includes an E2E test that attempts to exercise both backends in a single run.
It targets the two Postfix services using SMTP ports `1025` (Postgres) and `1026` (DB2):

```
pytest -q tests/test_e2e.py
```

If any backend is not available, the corresponding parameterized test will be skipped.

## Continuous Integration

GitHub Actions workflow is provided at `.github/workflows/ci.yml` with three jobs:

- Unit: Runs `pytest -m unit`.
- Backend: Starts DB backends via Docker Compose, then runs `pytest -m backend`.
- E2E: Starts full stack (both postfix services) and runs `pytest -m e2e`.

## JetBrains IDEs

- Use a local PyCharm data source (not shared in VCS).
- Create it via Database tool window or edit `.idea/dataSources.local.xml`.
- Connection details: host `localhost`, port `5433`, db `blocker`, user `blocker`.
- Passwords are stored locally; when prompted, enter `blocker`. If adding manually, leave password blank and let PyCharm store it via Keychain/Keyring.
