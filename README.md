# Postfix Blocker

This project provides a Python service and Angular web UI for managing a block
list of email recipients for Postfix. Blocked addresses are stored in a
database and automatically applied to Postfix, preventing delivery to those
recipients.

AGENTS.md contains development instructions for AI agents. 

The service uses SQLAlchemy and can connect to PostgreSQL or DB2
(install the optional `ibm-db-sa` package for DB2 support).

## Components

* **Python service (`app/blocker.py`)** – Monitors the database table and
  rewrites Postfix access maps when changes occur.
* **Flask API (`app/api.py`)** – REST API used by the Angular UI to manage
  blocked addresses.
* **Angular UI (`frontend`)** – Simple interface to view, add, and remove
  entries.
* **Docker Compose environment** – Includes Postfix, PostgreSQL, and MailHog
  for local testing.

## Running locally

```bash
docker compose up --build
```

The API is available on [http://localhost:5001](http://localhost:5001) and
MailHog's UI on [http://localhost:8025](http://localhost:8025).

PostgreSQL listens on port `5433` on the host to avoid conflicts with any
local installations.

## Testing

Run unit tests:

```bash
pytest
```

## End-to-end demo

The `tests/e2e_demo.py` script demonstrates blocking behaviour by sending
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
```

Troubleshooting Postfix SMTP:
- Ensure PCRE map support is installed in the image (we install `postfix-pcre`).
- Disable smtpd chroot in containers: set `smtp/inet/chroot = n` (done in Dockerfile).
- Verify SMTP is listening: `docker compose exec postfix nc -vz 127.0.0.1 25`.
- The dev image allows relaying from the host by setting `mynetworks = 0.0.0.0/0` for convenience. Do NOT use this setting in production; restrict `mynetworks` appropriately.

The script populates the database with a couple of blocked addresses, sends
three messages, and prints which recipients were actually delivered to
MailHog (only the allowed recipient should arrive).

## JetBrains IDEs

- Use a local PyCharm data source (not shared in VCS).
- Create it via Database tool window or edit `.idea/dataSources.local.xml`.
- Connection details: host `localhost`, port `5433`, db `blocker`, user `blocker`.
- Passwords are stored locally; when prompted, enter `blocker`. If adding manually, leave password blank and let PyCharm store it via Keychain/Keyring.
