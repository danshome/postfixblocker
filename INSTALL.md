<!-- Updated to best practices on 2025-09-14. -->
# Install & Setup

<!-- BEGIN GENERATED: INSTALL:MAIN -->

This guide walks through prerequisites and step-by-step installation.

## Prerequisites

| OS | Tooling |
|----|---------|
| macOS/Linux/WSL | Docker, Docker Compose, Python {{MIN_SUPPORTED_VERSIONS}} |

## Steps

```bash
# Clone
git clone https://github.com/{{ORG_NAME}}/{{PROJECT_NAME}}.git
cd {{PROJECT_NAME}}

# Start stack (DB, API, Postfix, MailHog)
docker compose up --build -d

# Verify API
curl -s http://localhost:5001/addresses
```

## Environment Configuration

Create a `.env` file or export variables:

```env
# .env.example
BLOCKER_DB_URL=postgresql://blocker:blocker@localhost:5433/blocker
SMTP_HOST=localhost
SMTP_PORT=1025
MAILHOG_HOST=localhost
MAILHOG_PORT=8025
```

## Troubleshooting

- DB2 slow startup: the DB2 container can take minutes to initialize. The
  blocker process retries until ready. Check `docker compose logs db2`.
- Ports in use: change host ports in `docker-compose.yml` or stop conflicting
  services.
- API 503 "database not ready": wait for DB readiness; the API serves 503
  until the schema is initialized.

<!-- END GENERATED: INSTALL:MAIN -->

