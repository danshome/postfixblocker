# Installing postfix-blocker on Red Hat Enterprise Linux 9.5

This guide explains how to deploy postfix-blocker on RHEL 9.5 using the
published release artifacts. Two paths are provided:

1. **Automated install script (recommended)** — fetches release artifacts,
   prepares the host (packages, user, directories), installs the Python wheel,
   writes systemd units, and optionally updates Postfix recipient restrictions.
2. **Manual installation reference** — detailed steps matching what the script
   performs behind the scenes when you need to customise every action.

Whichever path you choose, ensure you have:
- Control over the RHEL host (sudo access) and an existing Postfix instance.
- IBM Db2 11.5+ available with credentials permitted to create/update the
  `CRISOP` schema.
- Time to verify the deployment (Postfix reload, API call, log tail).

## Automated installation (recommended)

The installer script lives in the repository at `scripts/install.sh` and is
included in every release (wheel + source tarball under `share/postfixblocker`).
It behaves similarly to the Homebrew installer: you download and execute it as
root, optionally providing flags to customise the deployment.

> **Security note**: Always review the script before piping it to `bash`.

### 1. Gather Db2 connection details

Collect the following values (placeholders shown):

| Variable | Example | Notes |
|----------|---------|-------|
| Host     | `db.op` | default used by E2E installer test |
| Port     | `51200` | default used by installer test |
| Database | `BLOCKER` | |
| Schema   | `CRISOP` | required for our migrations |
| Username | `blocker_user` | must have DDL + DML rights |
| Password | `replace-me` | store securely |

The script expects a SQLAlchemy Db2 URL such as:

```
ibm_db_sa://blocker_user:replace-me@db.op:51200/BLOCKER?currentSchema=CRISOP
```

### 2. Run the installer

Example interactive install using the latest release, configuring Postfix, and
enabling services immediately:

```bash
sudo /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/danshome/postfixblocker/main/scripts/install.sh)" -- \
  --db-url ibm_db_sa://blocker_user:replace-me@db.op:51200/BLOCKER?currentSchema=CRISOP \
  --postfix-mode configure
```

Important options:

| Flag | Purpose |
|------|---------|
| `--db-url` | Required in non-interactive mode; otherwise prompted. |
| `--version` | Pin to a specific release (default: latest GitHub tag). |
| `--prefix` | Installation root (`/opt/postfixblocker` by default). |
| `--postfix-mode` | `configure` updates `smtpd_recipient_restrictions`; `skip` leaves Postfix untouched. |
| `--systemd-mode` | `enable` (default) reloads systemd, enables, and starts services; `write-only` writes unit files but leaves activation to you. |
| `--skip-db2-driver-check` | Allows the install to proceed even if `/opt/ibm/db2/current` is missing (useful during dry runs). |
| `--tarball-path`/`--wheel-path` | Use pre-downloaded artifacts for air-gapped installs. |

### 3. Script behaviour summary

The installer executes the following tasks:

- Enables CodeReady Builder (or CRB) and installs required RPMs via `dnf`
  (curl, tar, Python 3, build deps, Postfix, firewalld, etc.).
- Creates the `postfixblocker` system account, directories under
  `/opt/postfixblocker`, `/var/log/postfixblocker`, and `/var/run/postfix-blocker`.
- Downloads (or consumes provided) wheel + source tarball for the requested
  version, extracts application assets (including `sql/db2_init.sql`).
- Creates a virtual environment, installs postfix-blocker + gunicorn, and writes
  `/opt/postfixblocker/.env` using the provided Db2 URL.
- Writes systemd unit files for the blocker and API; optionally enables them.
- Optionally updates Postfix recipient restrictions (when `--postfix-mode configure`).

After the script completes, run:

```bash
sudo systemctl status postfixblocker-blocker postfixblocker-api
sudo journalctl -u postfixblocker-blocker -u postfixblocker-api -n 50
curl -s http://127.0.0.1:5000/addresses | jq .
```

### 4. Non-interactive automation example

For CI or air-gapped installs, download artifacts in advance and pass them to
the script. The new end-to-end test (`tests/test_install_e2e.py`) validates this
flow inside a Rocky Linux 9 container using env vars sourced from
`docker/install-test.env` (host `db.op`, port `51200`, schema `CRISOP`, and
placeholder credentials).

> **Apple Silicon note:** when testing inside Docker on macOS/arm64, add
> `--platform linux/amd64` to `docker run` so the container matches the
> architecture supported by the prebuilt `ibm_db` wheels.

```bash
sudo ./scripts/install.sh --non-interactive --version 0.0.1 \
  --db-url ibm_db_sa://blocker_user:replace-me@db.op:51200/BLOCKER?currentSchema=CRISOP \
  --tarball-path /tmp/postfix_blocker-0.0.1.tar.gz \
  --wheel-path /tmp/postfix_blocker-0.0.1-py3-none-any.whl \
  --systemd-mode write-only --postfix-mode skip --skip-db2-driver-check
```

## Manual installation reference

The sections below mirror what the script automates. Follow them if you prefer
to control each step manually or need to integrate with an existing
configuration management workflow.

### 1. Pre-install checklist

Before touching the system, confirm the following:
- **Postfix** is installed locally and you can reload it without disrupting
  production traffic. Regex rules require PCRE map support (`postfix-pcre`).
- **Db2 connectivity** is available from this host (firewall open to TCP 50000
  or your custom port). You know the JDBC/SQLAlchemy style URL components:
  hostname, port, database name, username, and password.
- **System access**: you can add packages, create system users, and install
  files under `/opt`, `/etc/systemd/system`, `/var/log`, and `/etc/postfix`.
- **Time synchronization** is in place. The blocker compares timestamps when
  deciding whether to refresh maps.
- **Backups** exist for `/etc/postfix/main.cf` and any custom access maps in
  case you need to roll back.

### 2. Prepare the operating system

Enable the CodeReady Builder (CRB) channel and install the packages required to
run postfix-blocker, compile its drivers, and manage services.

```bash
sudo subscription-manager repos --enable codeready-builder-for-rhel-9-$(/usr/bin/arch)-rpms
sudo dnf install -y --allowerasing \
  curl tar \
  policycoreutils-python-utils \
  python3 python3-devel python3-pip \
  gcc make \
  openssl-devel libffi-devel \
  postfix postfix-pcre \
  firewalld \
  git  # optional: only needed if you want to inspect sources
```

Verify Postfix PCRE support and service status:

```bash
postconf -m | grep -qi pcre && echo "PCRE map support detected" || {
  echo "ERROR: Postfix PCRE support missing. Install postfix-pcre before continuing." >&2
  exit 1
}
systemctl status postfix --no-pager || sudo systemctl start postfix
```

### 3. Install the IBM Data Server Driver (Db2 CLI)

The Python `ibm_db` module bundled with postfix-blocker needs the Db2 CLI
runtime. Download the "IBM Data Server Driver for ODBC and CLI" package for
Linux x64 from IBM Fix Central (IBM ID required). Place the archive under
`/tmp` and unpack it to `/opt/ibm/db2/clidriver`.

```bash
sudo mkdir -p /opt/ibm/db2
cd /opt/ibm/db2
sudo tar -xzf /tmp/ibm_data_server_driver_for_odbc_cli_linuxx64_v*.tar.gz
sudo mv clidriver current
sudo chown -R root:root /opt/ibm/db2/current
```

Expose the driver location to the environment used by postfix-blocker. The
simplest approach is to drop a profile script:

```bash
cat | sudo tee /etc/profile.d/postfixblocker-db2.sh >/dev/null <<'EOF'
export IBM_DB_HOME=/opt/ibm/db2/current
export LD_LIBRARY_PATH=/opt/ibm/db2/current/lib:$LD_LIBRARY_PATH
