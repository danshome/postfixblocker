<!-- Updated to best practices on 2025-09-14. -->
# FAQ

<!-- BEGIN GENERATED: FAQ:MAIN -->

## Does this support DB2?
Yes. This project now supports DB2 only. See `BLOCKER_DB_URL` examples in
`docker-compose.yml` and [INSTALL](INSTALL.md).

## Why do e2e tests fail if DB2 is slow to start?
DB2 can be slow to initialize. Ensure the DB2 container is `healthy` before running tests.
See `tests/utils_wait.py` and run with `E2E_DEBUG=1` for more info.

## How do I reset the database?
Use the backend smoke tests or connect with a SQL client and truncate
`blocked_addresses`. The e2e script seeds data on each run.

## How do I add a blocked address?

```bash
curl -X POST http://localhost:5002/addresses \
  -H 'Content-Type: application/json' \
  -d '{"pattern":"user@example.com","is_regex":false}'
```

## How do I run the Postfix service?
Use the `postfix` service (DB2-only).

## Why does the API return 503 sometimes?
It returns `{"error":"database not ready"}` until the database is reachable
and the schema is created.

## Where are the Postfix maps written?
Inside the container at `/etc/postfix/blocked_recipients` and
`/etc/postfix/blocked_recipients.pcre`.

## How do I run frontend tests?

```bash
cd frontend
npm install
npm test
```

## How do I run e2e UI tests?

```bash
cd frontend
npm run e2e
```

## Where to get help?
See [SUPPORT](SUPPORT.md) and {{DISCUSS_URL}}.

## What is the default admin password the first time?
- Username: `admin` by default (configurable via `ADMIN_USERNAME`).
- Initial password: `postfixblocker`.

On first successful login with the default password, the API will return `mustChangePassword: true` and the UI will prompt you to set a new password before you can continue. This applies when authentication is enforced (set `API_AUTH_REQUIRED=1` for the API process).

<!-- END GENERATED: FAQ:MAIN -->
