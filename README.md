# Postfix Blocker

This project provides a Python service and Angular web UI for managing a block
list of email recipients for Postfix. Blocked addresses are stored in a
database and automatically applied to Postfix, preventing delivery to those
recipients.

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

## End-to-end test

An experimental script `tests/e2e_demo.py` was intended to demonstrate
blocking behaviour by sending emails through Postfix and verifying delivery via
MailHog. The script currently hangs and is not functional.
