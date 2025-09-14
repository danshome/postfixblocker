# Postfix Blocker

This project provides a Python service and Angular web UI for managing a block
list of email recipients for Postfix. Blocked addresses are stored in a
database and automatically applied to Postfix, preventing delivery to those
recipients.

AGENTS.md contains development instructions for AI agents.

The service uses SQLAlchemy and supports PostgreSQL and IBM DB2 11.5.
For DB2 support, Python dependencies `ibm-db` and `ibm-db-sa` are required
(already listed in `requirements.txt`).

## Components

* **Python service (`app/blocker.py`)** – Monitors the database table and
  rewrites Postfix access maps when changes occur.
* **Flask API (`app/api.py`)** – REST API used by the Angular UI to manage
  blocked addresses.
* **Angular UI (`frontend`)** – Simple interface to view, add, and remove
  entries.
* **Docker Compose environment** – Includes Postfix, PostgreSQL, IBM DB2 (optional),
  and MailHog for local testing.

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
architectures (e.g., Apple Silicon). The compose file pins services to
`linux/amd64` for reliable DB2 support.

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

## Testing

Run unit tests:

```bash
pytest
```

Markers to scope runs:

- Unit: `pytest -m unit`
- Backend (requires Docker DBs): `pytest -m backend`
- E2E (requires full stack): `pytest -m e2e`

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
docker compose cp tests/e2e_test.py postfix:/opt/app/e2e_run.py
docker compose exec postfix env \
  BLOCKER_DB_URL=postgresql://blocker:blocker@db:5432/blocker \
  SMTP_HOST=127.0.0.1 SMTP_PORT=25 \
  MAILHOG_HOST=mailhog MAILHOG_PORT=8025 \
  python /opt/app/e2e_run.py
```

Mass traffic demo
- Simulate hundreds of emails (allowed + blocked), and block an allowed address mid-stream to prove the live blocker works:

```bash
# From host
python tests/e2e_test.py --mass --total 300

# Inside the postfix container (recommended if host DB port is blocked)
docker compose cp tests/e2e_test.py postfix:/opt/app/e2e_run.py
docker compose exec postfix env \
  BLOCKER_DB_URL=postgresql://blocker:blocker@db:5432/blocker \
  SMTP_HOST=127.0.0.1 SMTP_PORT=25 \
  MAILHOG_HOST=mailhog MAILHOG_PORT=8025 \
  python /opt/app/e2e_run.py --mass --total 300

Using DB2 instead of Postgres inside the postfix container:

```
docker compose exec postfix env \
  BLOCKER_DB_URL=ibm_db_sa://db2inst1:blockerpass@db2:50000/BLOCKER \
  SMTP_HOST=127.0.0.1 SMTP_PORT=25 \
  MAILHOG_HOST=mailhog MAILHOG_PORT=8025 \
  python /opt/app/e2e_run.py
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
