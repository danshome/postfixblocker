<!-- Updated to best practices on 2025-09-14. -->
# Install & Setup

<!-- BEGIN GENERATED: INSTALL:MAIN -->

This guide walks through prerequisites and step-by-step installation for
development and production.

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

<!-- BEGIN GENERATED: INSTALL:PROD_RHEL9_5 -->

## Production Deployment (RHEL 9.5, no Docker)

This section describes how to run only the Python blocker (`postfix_blocker/blocker.py`)
and API (`postfix_blocker/api.py`) on a RHEL 9.5 host where Postfix is already installed
and the database runs on a separate server. The Angular UI is optional and is
not covered here.

### Overview

- The blocker service watches the `blocked_addresses` table and writes
  Postfix maps under `/etc/postfix`, then triggers `postfix reload`.
- The API exposes `/addresses` for CRUD operations. Run it behind a
  production WSGI server such as `gunicorn` (recommended) or restrict the
  built-in Flask server to localhost.

### 1) OS prerequisites (RHEL 9.5)

First, verify what is already installed on your RHEL 9.5 host. Only install
packages if something is missing.

```bash
# Postfix installed?
rpm -q postfix || echo "postfix: NOT INSTALLED"

# Does Postfix support PCRE maps? (required for regex rules)
postconf -m | grep -qi pcre && echo "PCRE support: OK" || echo "PCRE support: MISSING"

# Optional: show Postfix service status (does not fail the script)
systemctl status postfix --no-pager || true
```

If Postfix is not installed or PCRE support is missing, install the required
packages. On RHEL 9.5, enable the CodeReady Builder repo via subscription-manager if needed.

```bash
# Ensure you have an active RHEL subscription and subscription-manager configured
sudo subscription-manager status || true

# Optional: list repos and check for CodeReady Builder
sudo subscription-manager repos --list | egrep -i 'codeready|builder' || true

# Enable CodeReady Builder (RHEL 9.5)
sudo subscription-manager repos --enable codeready-builder-for-rhel-9-$(/bin/arch)-rpms || true

# Install Postfix with PCRE support
sudo dnf install -y postfix postfix-pcre

# Re-verify PCRE support after install
postconf -m | grep -qi pcre || {
  echo "ERROR: Postfix PCRE map support is still missing." >&2
  echo "On RHEL 9.5, PCRE is typically built in or provided by postfix-pcre. If still missing, install the appropriate PCRE support package or rebuild Postfix with PCRE enabled." >&2
  exit 1
}
```

Verify your existing `main.cf` contains appropriate recipient restrictions.
If you need to add the blocker maps, plan the change carefully to preserve
your current policy. Example (adjust to your environment):

```bash
# Example only — merge into your existing policy
sudo postconf -e \
  'smtpd_recipient_restrictions = \
   check_recipient_access hash:/etc/postfix/blocked_recipients, \
   check_recipient_access pcre:/etc/postfix/blocked_recipients.pcre, \
   permit_mynetworks, reject_unauth_destination'
```

SELinux: Writing map files in `/etc/postfix` and running `postmap`/`postfix reload`
should work with the default contexts. If custom SELinux policies are in place,
you may need to apply contexts for the generated files:

```bash
sudo semanage fcontext -a -t etc_t \
  "/etc/postfix/blocked_recipients(\.pcre)?(\.db)?"
sudo restorecon -Rv /etc/postfix
```

### 2) Create a deployment directory and Python environment

```bash
sudo mkdir -p /opt/postfixblocker
sudo chown -R $USER:$USER /opt/postfixblocker
cd /opt/postfixblocker

# Clone or copy the repository here
git clone https://github.com/{{ORG_NAME}}/{{PROJECT_NAME}}.git .

# Create a virtualenv
python3 -m venv venv
source venv/bin/activate

# Install minimal runtime deps
pip install --upgrade pip
# Option A: PostgreSQL only
pip install -r requirements-base.txt psycopg2-binary gunicorn
# Option B: DB2 support
pip install -r requirements-base.txt -r requirements-db2.txt gunicorn

# Validate drivers as needed
python -c 'import sqlalchemy, sys; print("SQLAlchemy", sqlalchemy.__version__)'
```

Note for DB2: The `ibm-db` wheels typically include the required client
libraries. If installation fails, consult IBM documentation for installing the
IBM Data Server Driver and setting `IBM_DB_HOME`.

DB2 page size requirement for CRIS_PROPS
---------------------------------------
The production schema uses a 1024 OCTETS PRIMARY KEY on CRISOP.CRIS_PROPS.
On Db2 LUW, the index key length is constrained by the tablespace page size.
To avoid SQL0613N (key too long), you must use a 32K tablespace (or at least 8K/16K
depending on your environment) for the table and its primary key index.

We provide `sql/db2_init.sql` which:
- Creates a 32K bufferpool and a 32K automatic storage tablespace.
- Creates the application tables in that tablespace.
- Creates CRISOP.CRIS_PROPS with its PK index in the 32K tablespace.

Run this script against a clean database as a user with sufficient privileges:

```bash
# From a Db2 CLP-enabled shell
db2 connect to BLOCKER user db2inst1 using 'password'
db2 -tvf sql/db2_init.sql
```

If your environment already has CRISOP schema and tablespaces,
you can adapt the script names or pre-create the 32K tablespace and run only the
CREATE TABLE statements with `IN <your_32k_ts> INDEX IN <your_32k_ts>`.

If your DB URL does not specify a schema, set the current schema so unqualified
references resolve to CRISOP (optional but recommended):

```bash
export BLOCKER_DB_URL="ibm_db_sa://db2inst1:password@db2:50000/BLOCKER?currentSchema=CRISOP"
```

### 3) Configure environment

Create a `.env` file for the services:

```bash
cat > /opt/postfixblocker/.env <<'EOF'
# Database URL (choose one)
#BLOCKER_DB_URL=postgresql://user:pass@db.example.com:5432/blocker
#BLOCKER_DB_URL=ibm_db_sa://db2inst1:password@db2.example.com:50000/BLOCKER

# Polling interval in seconds for the blocker
BLOCKER_INTERVAL=5

# Postfix configuration directory
POSTFIX_DIR=/etc/postfix

# API port (bind via gunicorn; see systemd unit below)
PORT=5000
EOF
```

### 4) Systemd services

Create systemd units for the blocker and API. Adjust `User=` to your
operational preference. Running the blocker as `root` is simplest because it
invokes `postmap` and `postfix reload`. For a non-root user, configure
`sudoers` to allow those commands without a password.

Blocker service (`/etc/systemd/system/postfixblocker-blocker.service`):

```ini
[Unit]
Description=Postfix Blocker (writes maps, reloads postfix)
Wants=network-online.target
After=network-online.target postfix.service
Requires=postfix.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/postfixblocker
EnvironmentFile=/opt/postfixblocker/.env
ExecStart=/opt/postfixblocker/venv/bin/python -m postfix_blocker.blocker
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
```

API service with gunicorn (`/etc/systemd/system/postfixblocker-api.service`):

```ini
[Unit]
Description=Postfix Blocker API (Flask via gunicorn)
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User={{PROJECT_NAME}}  # TODO: replace or use a service account
WorkingDirectory=/opt/postfixblocker
EnvironmentFile=/opt/postfixblocker/.env
ExecStart=/opt/postfixblocker/venv/bin/gunicorn -w 2 -b 127.0.0.1:${PORT} postfix_blocker.api:app
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
```

Reload and start services:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now postfixblocker-blocker.service
sudo systemctl enable --now postfixblocker-api.service
```

### 5) (Optional) Reverse proxy for the API

Expose the API via NGINX or Apache. Example NGINX server block:

```nginx
server {
  listen 80;
  server_name blocker.example.com;
  location / {
    proxy_pass http://127.0.0.1:5000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
  }
}
```

### 6) Verification

1. Confirm map files after the blocker starts:
   - `/etc/postfix/blocked_recipients`
   - `/etc/postfix/blocked_recipients.pcre`
   - `/etc/postfix/blocked_recipients.db` (created by `postmap`)
2. Check Postfix logs for a successful reload (on RHEL 9.5, logs are in /var/log/maillog).
3. Call the API:

```bash
curl -s http://127.0.0.1:5000/addresses | jq .
```

Add a test entry (replace port/host if proxied):

```bash
curl -s -X POST http://127.0.0.1:5000/addresses \
  -H 'Content-Type: application/json' \
  -d '{"pattern":"blocked@example.com","is_regex":false}'
```

### 7) Optional: run blocker without root

Create `/etc/sudoers.d/postfixblocker` to grant the required commands:

```
postfixblocker ALL=(root) NOPASSWD: /usr/sbin/postmap /etc/postfix/blocked_recipients,
                                     /usr/sbin/postfix reload
```

Then set `User=postfixblocker` in the blocker unit. Note: the current code
invokes `postmap`/`postfix` directly; if running unprivileged, ensure the
`sudoers` entries are correct and that `sudo` is on the PATH for the service
or provide wrapper scripts.

### Notes on PCRE requirement and behavior

- The API (`postfix_blocker/api.py`) does not require Postfix PCRE support and will run
  regardless.
- The blocker (`postfix_blocker/blocker.py`) writes both the hash and PCRE map files and
  runs `postmap` only on the hash map (PCRE maps are plain text). It then
  executes `postfix reload`.
- If PCRE support is missing and your `main.cf` references the PCRE map, the
  reload will fail and regex rules will not be enforced. The blocker logs the
  error but keeps running. For full functionality, ensure PCRE support is
  present and that `postconf -m` lists `pcre`.

### 8) Firewalld

If exposing the API externally via a reverse proxy on port 80/443, open the
appropriate services. The blocker itself does not require inbound ports.

```bash
sudo firewall-cmd --add-service=http --permanent
sudo firewall-cmd --add-service=https --permanent
sudo firewall-cmd --reload
```

<!-- END GENERATED: INSTALL:PROD_RHEL9_5 -->
