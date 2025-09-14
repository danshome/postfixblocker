<!-- Updated to best practices on 2025-09-14. -->
# FAQ

<!-- BEGIN GENERATED: FAQ:MAIN -->

## Does this support DB2 and PostgreSQL?
Yes. SQLAlchemy abstracts both backends. See `BLOCKER_DB_URL` examples in
`docker-compose.yml` and [INSTALL](INSTALL.md).

## Why do e2e tests sometimes skip DB2?
DB2 can be slow to start. Tests skip when services aren’t ready. See
`tests/utils_wait.py` and run with `E2E_DEBUG=1` for more info.

## How do I reset the database?
Use the backend smoke tests or connect with a SQL client and truncate
`blocked_addresses`. The e2e script seeds data on each run.

## How do I add a blocked address?

```bash
curl -X POST http://localhost:5001/addresses \
  -H 'Content-Type: application/json' \
  -d '{"pattern":"user@example.com","is_regex":false}'
```

## How do I enable DB2 in the Postfix service?
Either use the `postfix_db2` service or set `BLOCKER_DB_URL` in `postfix` to a
DB2 URL and rebuild.

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

<!-- END GENERATED: FAQ:MAIN -->

