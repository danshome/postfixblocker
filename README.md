<!-- Updated to best practices on 2025-09-14; preserves project-specific content. -->
# Postfix Blocker

<!-- BEGIN GENERATED: README:STANDARD_BLOCK -->

[![Latest Release](https://img.shields.io/github/v/release/danshome/postfixblocker?display_name=tag&sort=semver)](https://github.com/danshome/postfixblocker/releases)
[![CI Status](https://github.com/danshome/postfixblocker/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/danshome/postfixblocker/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/endpoint?url=https%3A%2F%2Fraw.githubusercontent.com%2Fdanshome%2Fpostfixblocker%2Fgh-pages%2Fbadges%2Fcoverage.json&cacheSeconds=3600)](https://github.com/danshome/postfixblocker/actions)
[![Python Versions](https://img.shields.io/badge/python-3.9%2B-blue.svg)](pyproject.toml)
[![License](https://img.shields.io/github/license/danshome/postfixblocker.svg)](LICENSE)

This repository is owned by danshome and the canonical project name is
postfix-blocker (PyPI package; GitHub repo: postfixblocker). The primary
language is Python and the minimum supported toolchain is: Python 3.9+ and
Node.js 18+ (for the Angular frontend).

## At‑a‑Glance

- Key features:
  - API + background service to manage a Postfix recipient blocklist.
  - Supports IBM DB2 11.5 via SQLAlchemy.
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
docker compose logs -f postfix_db2
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
curl -s http://localhost:5002/addresses | jq .
```

Add and delete an address:

```bash
curl -X POST http://localhost:5002/addresses \
  -H 'Content-Type: application/json' \
  -d '{"pattern":"user@example.com","is_regex":false, "test_mode":true}'

curl -X DELETE http://localhost:5002/addresses/1
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

The service uses SQLAlchemy and supports IBM DB2 11.5.
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
* **Docker Compose environment** – Includes Postfix (DB2-backed) and MailHog for local testing.

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

The API is available on [http://localhost:5002](http://localhost:5002) and
MailHog's UI on [http://localhost:8025](http://localhost:8025).

IBM DB2 listens on port `50000`. One Postfix service is available:

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

### Database backend

- IBM DB2 11.5:
  - Service: `db2` (icr.io/db2_community/db2:11.5.8.0)
  - Accepts license via `LICENSE=accept` env
  - Default credentials in compose: user `db2inst1`, db `BLOCKER`, password `blockerpass`
  - URL examples:
    - `ibm_db_sa://db2inst1:blockerpass@localhost:50000/BLOCKER`
    - `db2+ibm_db://db2inst1:blockerpass@localhost:50000/BLOCKER`
  - Note: DB2 container typically requires several GB of RAM and runs in
    privileged mode in the sample compose for simplicity in dev.
  - Architecture note: DB2 Python drivers are installed only on x86_64. On
    arm64 (e.g., Apple Silicon) local builds may skip driver install.

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
docker compose build postfix_db2
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
npm run e2e  # runs against DB2 (starts dev server on 4200)
```

Notes:
- API: use `npm run start:db2` (or `npm start`) which uses `frontend/proxy.json` to proxy to `http://localhost:5002`.
- DB2 container can take a few minutes to initialize. If you see proxy ECONNRESET errors, wait until `curl http://localhost:5002/addresses` returns `[]` and refresh.

Run e2e against DB2 only (optional):

```
cd frontend
npm run e2e:db2
```

This runs the DB2 Playwright project. The test runner starts the dev server on port 4200 and proxies to the API on port 5002.

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
- The dev server proxies `/addresses` to the host API (default `http://localhost:5002`). Ensure `docker compose up` is running.

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
- Postfix exposes SMTP on host `localhost:1026`

Run from the repository root so the `app` package can be imported:

```bash
python tests/e2e_test.py
```

Configuration via environment variables (optional):
- `BLOCKER_DB_URL` (default `ibm_db_sa://db2inst1:blockerpass@localhost:50000/BLOCKER`)
- `SMTP_HOST`/`SMTP_PORT` (defaults `localhost`/`1026`)
- `MAILHOG_HOST`/`MAILHOG_PORT` (defaults `localhost`/`8025`)

Running inside the Postfix container (useful on some hosts):

```bash
docker compose cp tests/e2e_test.py postfix_db2:/opt/postfix_blocker/e2e_run.py
docker compose exec postfix_db2 env \
  BLOCKER_DB_URL=ibm_db_sa://db2inst1:blockerpass@db2:50000/BLOCKER \
  SMTP_HOST=127.0.0.1 SMTP_PORT=25 \
  MAILHOG_HOST=mailhog MAILHOG_PORT=8025 \
  python /opt/postfix_blocker/e2e_run.py
```

Mass traffic demo
- Simulate hundreds of emails (allowed + blocked), and block an allowed address mid-stream to prove the live blocker works:

```bash
# From host
python tests/e2e_test.py --mass --total 300

# Inside the postfix_db2 container (recommended if host DB port is blocked)
docker compose cp tests/e2e_test.py postfix_db2:/opt/postfix_blocker/e2e_run.py
docker compose exec postfix_db2 env \
  BLOCKER_DB_URL=ibm_db_sa://db2inst1:blockerpass@db2:50000/BLOCKER \
  SMTP_HOST=127.0.0.1 SMTP_PORT=25 \
  MAILHOG_HOST=mailhog MAILHOG_PORT=8025 \
  python /opt/postfix_blocker/e2e_run.py --mass --total 300


Troubleshooting Postfix SMTP:
- Ensure PCRE map support is installed in the image (we install `postfix-pcre`).
- Disable smtpd chroot in containers: set `smtp/inet/chroot = n` (done in Dockerfile).
- Verify SMTP is listening: `docker compose exec postfix_db2 nc -vz 127.0.0.1 25`.
- The dev image allows relaying from the host by setting `mynetworks = 0.0.0.0/0` for convenience. Do NOT use this setting in production; restrict `mynetworks` appropriately.

The script populates the database with a couple of blocked addresses, sends
three messages, and prints which recipients were actually delivered to
MailHog (only the allowed recipient should arrive).

## Backend tests

Backend smoke tests can be run by setting environment variables:

```
TEST_DB2_URL=ibm_db_sa://db2inst1:blockerpass@localhost:50000/BLOCKER pytest -q tests/test_db_backends.py
```

## E2E tests

Pytest includes an E2E test that exercises the DB2-backed postfix service on SMTP port `1026`:

```
pytest -q tests/test_e2e.py
```

## Continuous Integration

GitHub Actions workflow is provided at `.github/workflows/ci.yml` with three jobs:

- Unit: Runs `pytest -m unit`.
- Backend: Starts DB2 via Docker Compose, then runs `pytest -m backend`.
- E2E: Starts full stack (postfix_db2) and runs `pytest -m e2e`.

## JetBrains IDEs

- Use a local data source for DB2 (not shared in VCS).
- Create it via Database tool window or edit `.idea/dataSources.local.xml`.
- Connection details: host `localhost`, port `50000`, db `BLOCKER`, user `db2inst1`.
- Passwords are stored locally; when prompted, enter `blockerpass` (or your configured password).



## DB2 initialization: persist data without rebuilding every time

The official `ibmcom/db2` image initializes the DB2 instance and creates the database on the first run. To avoid doing that heavy initialization on every start, you must persist `/database` across container restarts.

What we use by default:
- In `docker-compose.yml`, the `db2` service now uses a named Docker volume:
  - `db2data:/database`
- This avoids cross‑OS permission issues that can happen with bind mounts (e.g., `useradd: cannot create directory /database/config/db2inst1`).
- Data persists across restarts. To reset it:
  - `docker compose stop` (to stop containers without removing them)
  - `docker volume rm $(docker compose ls -q | xargs -I {} echo {}_db2data || true)` (or inspect `docker volume ls` and remove the `db2data` volume for this project)

If you prefer a host directory (advanced):
- You can switch the mapping to `./db2data:/database`, but make sure permissions are correct on the host. A safe setup is:
  - `rm -rf ./db2data && mkdir -p ./db2data/config`
  - `chmod -R 777 ./db2data` (or `chown -R $(id -u):$(id -g) ./db2data` and ensure Docker can write)
  - Do not commit `db2data/` into Git; add it to `.gitignore`.
- If you previously used a bind mount and see `d---------` directories inside `db2data/config` (zero permissions), delete the folder or fix the permissions before starting DB2 again.

### Can we bake a pre-initialized DB2 image?

You generally shouldn’t try to run the full DB2 engine during `docker build`; the official image performs initialization at container runtime. If you need a reusable pre-initialized image for CI, you can create one manually and push it to a registry:

1. Start DB2 once so it initializes the instance and database:
   - `docker compose up -d db2`
   - Wait until `docker compose ps` shows `healthy`.
2. Commit the initialized container into a new image (replace `<id>` with the container ID):
   - `docker commit <id> your-registry/postfixblocker-db2:preinit`
3. Push it to your registry and update `docker-compose.yml`'s `db2` service to use `image: your-registry/postfixblocker-db2:preinit` (you can remove the volume mapping if you want the image’s baked data). Accept the license in your environment as required by IBM’s terms.

This approach can reduce CI startup time. For local development, the default named volume (`db2data`) is simpler and avoids host permission pitfalls.



## Logging endpoints (API)

The API exposes several endpoints to inspect and control logging:

- GET /logs/tail?name={api|blocker|postfix}&lines=N
  Returns the last N lines of the selected log. Response JSON: { name, path, content, missing }.

- GET /logs/lines?name={api|blocker|postfix}
  Returns the current line count for the selected log. Response JSON: { name, path, count, missing }.

- GET/PUT /logs/level/{service}
  Get or set the log level for a service. Services: api, blocker, postfix.
  PUT body JSON: { "level": "WARNING|INFO|DEBUG|<number>" }.
  For service=api the in-process logger level is updated. For service=postfix,
  the relevant Postfix settings are written to main.cf and Postfix is reloaded.

- GET/PUT /logs/refresh/{name}
  Get or set UI refresh cadence and tail size. GET returns { name, interval_ms, lines }.
  PUT body JSON: { "interval_ms": number, "lines": number }.

### Postfix log level mapping

Postfix has a numeric `debug_peer_level`. The UI/API map to Postfix as follows:

- WARNING -> 1 (least verbose)
- INFO -> 2
- DEBUG -> 10 (for higher verbosity on builds that accept >4)
- Numeric strings are capped to 4 and floored to 1 (e.g., "7" -> 4, "0" -> 1)

TLS log verbosity is derived as:
- WARNING -> 0, INFO -> 1, DEBUG -> 4
- Numeric: >=4 -> 4, >=3 -> 1, else 0

The mail log path is resolved at runtime. You can override with env var `MAIL_LOG_FILE`.
