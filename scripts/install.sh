#!/bin/bash
# Automated installer for postfix-blocker on RHEL/Rocky 9 hosts.
# Supports interactive and non-interactive operation and can consume pre-downloaded
# release artifacts to simplify air-gapped installs and automated testing.

set -euo pipefail

APP_REPO="danshome/postfixblocker"
DEFAULT_PREFIX="/opt/postfixblocker"
APP_USER="postfixblocker"
LOG_DIR="/var/log/postfixblocker"
PID_DIR="/var/run/postfix-blocker"
DEFAULT_POSTFIX_DIR="/etc/postfix"

VERSION=""
PREFIX="$DEFAULT_PREFIX"
DB_URL=""
DB_URL_FOR_TEST=""
API_HOST="127.0.0.1"
API_PORT="5000"
POSTFIX_DIR="$DEFAULT_POSTFIX_DIR"
POSTFIX_MODE="skip"      # configure|skip
SYSTEMD_MODE="enable"     # enable|write-only|skip
NON_INTERACTIVE=0
SKIP_DB2_CHECK=0
TARBALL_PATH=""
WHEEL_PATH=""
FORCE=0
FRONTEND_HOST="0.0.0.0"
FRONTEND_PORT="4200"

SCRIPT_NAME="postfixblocker-install"

timestamp() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

log() {
  printf '[%s][%s] %s\n' "$SCRIPT_NAME" "$(timestamp)" "$*"
}

warn() {
  printf >&2 '[%s][%s][WARN] %s\n' "$SCRIPT_NAME" "$(timestamp)" "$*"
}

err() {
  printf >&2 '[%s][%s][ERROR] %s\n' "$SCRIPT_NAME" "$(timestamp)" "$*"
}

usage() {
  cat <<'USAGE_BLOCK'
Usage: install.sh [options]

Options:
  --version X.Y.Z            Install the specified release (default: latest GitHub release)
  --prefix DIR               Installation root (default: /opt/postfixblocker)
  --db-url URL               Db2 SQLAlchemy URL (prompted interactively if omitted)
  --api-host HOST            API bind address (default: 127.0.0.1)
  --api-port PORT            API bind port (default: 5000)
  --ui-host HOST             Frontend bind address (default: 0.0.0.0)
  --ui-port PORT             Frontend bind port (default: 4200)
  --postfix-dir DIR          Postfix configuration directory (default: /etc/postfix)
  --postfix-mode MODE        Postfix configuration: configure|skip (default: skip)
  --systemd-mode MODE        Systemd handling: enable|write-only|skip (default: enable)
  --tarball-path FILE        Use a local source tarball instead of downloading
  --wheel-path FILE          Use a local wheel instead of downloading
  --skip-db2-driver-check    Do not require /opt/ibm/db2/current to exist
  --non-interactive          Fail on missing inputs instead of prompting
  --force                    Overwrite existing installation (venv, app directory, .env)
  --help                     Show this help and exit

Examples:
  # Interactive install of latest release, configure Postfix, enable services
  sudo /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/danshome/postfixblocker/main/scripts/install.sh)" -- \
    --postfix-mode configure

  # Non-interactive install using already downloaded artifacts (air-gapped/testing)
  sudo ./scripts/install.sh --non-interactive --version 0.0.1 \
    --db-url ibm_db_sa://user:pass@db:50000/BLOCKER?currentSchema=CRISOP \
    --tarball-path /tmp/postfix_blocker-0.0.1.tar.gz \
    --wheel-path /tmp/postfix_blocker-0.0.1-py3-none-any.whl \
    --systemd-mode write-only --postfix-mode skip --skip-db2-driver-check
USAGE_BLOCK
}

db_url_summary() {
  if [ -z "$DB_URL" ]; then
    printf 'not provided'
    return
  fi
  local host
  host=$(printf '%s' "$DB_URL" | sed -E 's|.*://[^@]*@([^:/?]+).*|\1|')
  if [ -z "$host" ]; then
    host="unknown-host"
  fi
  printf 'provided (host=%s)' "$host"
}

log_configuration() {
  local tarball_source wheel_source
  if [ -n "$TARBALL_PATH" ]; then
    tarball_source="$TARBALL_PATH"
  else
    tarball_source='download'
  fi
  if [ -n "$WHEEL_PATH" ]; then
    wheel_source="$WHEEL_PATH"
  else
    wheel_source='download'
  fi

  log "Installation prefix: $PREFIX"
  log "Systemd mode: $SYSTEMD_MODE"
  log "Postfix mode: $POSTFIX_MODE (dir=$POSTFIX_DIR)"
  log "API binding: ${API_HOST}:${API_PORT}"
  log "Frontend binding: ${FRONTEND_HOST}:${FRONTEND_PORT}"
  log "Installer flags: non_interactive=$NON_INTERACTIVE force=$FORCE skip_db2_check=$SKIP_DB2_CHECK"
  log "Artifacts: tarball=${tarball_source}, wheel=${wheel_source}"
  log "Database URL: $(db_url_summary)"
}

require_root() {
  if [ "$(id -u)" -ne 0 ]; then
    err "Run this installer as root (use sudo)."
    exit 1
  fi
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    err "Required command '$1' is missing."
    exit 1
  fi
}

parse_args() {
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --version)
        VERSION="${2:-}"
        [ -n "$VERSION" ] || { err "--version requires a value"; exit 1; }
        shift 2
        ;;
      --prefix)
        PREFIX="${2:-}"
        [ -n "$PREFIX" ] || { err "--prefix requires a value"; exit 1; }
        shift 2
        ;;
      --db-url)
        DB_URL="${2:-}"
        [ -n "$DB_URL" ] || { err "--db-url requires a value"; exit 1; }
        shift 2
        ;;
      --api-host)
        API_HOST="${2:-}"
        [ -n "$API_HOST" ] || { err "--api-host requires a value"; exit 1; }
        shift 2
        ;;
      --api-port)
        API_PORT="${2:-}"
        [ -n "$API_PORT" ] || { err "--api-port requires a value"; exit 1; }
        shift 2
        ;;
      --ui-host)
        FRONTEND_HOST="${2:-}"
        [ -n "$FRONTEND_HOST" ] || { err "--ui-host requires a value"; exit 1; }
        shift 2
        ;;
      --ui-port)
        FRONTEND_PORT="${2:-}"
        [ -n "$FRONTEND_PORT" ] || { err "--ui-port requires a value"; exit 1; }
        shift 2
        ;;
      --postfix-dir)
        POSTFIX_DIR="${2:-}"
        [ -n "$POSTFIX_DIR" ] || { err "--postfix-dir requires a value"; exit 1; }
        shift 2
        ;;
      --postfix-mode)
        POSTFIX_MODE="${2:-}"
        [ -n "$POSTFIX_MODE" ] || { err "--postfix-mode requires a value"; exit 1; }
        case "$POSTFIX_MODE" in
          configure|skip) ;;
          *) err "Invalid --postfix-mode ($POSTFIX_MODE)"; exit 1 ;;
        esac
        shift 2
        ;;
      --systemd-mode)
        SYSTEMD_MODE="${2:-}"
        [ -n "$SYSTEMD_MODE" ] || { err "--systemd-mode requires a value"; exit 1; }
        case "$SYSTEMD_MODE" in
          enable|write-only|skip) ;;
          *) err "Invalid --systemd-mode ($SYSTEMD_MODE)"; exit 1 ;;
        esac
        shift 2
        ;;
      --tarball-path)
        TARBALL_PATH="${2:-}"
        [ -n "$TARBALL_PATH" ] || { err "--tarball-path requires a value"; exit 1; }
        shift 2
        ;;
      --wheel-path)
        WHEEL_PATH="${2:-}"
        [ -n "$WHEEL_PATH" ] || { err "--wheel-path requires a value"; exit 1; }
        shift 2
        ;;
      --skip-db2-driver-check)
        SKIP_DB2_CHECK=1
        shift
        ;;
      --non-interactive)
        NON_INTERACTIVE=1
        shift
        ;;
      --force)
        FORCE=1
        shift
        ;;
      --help|-h)
        usage
        exit 0
        ;;
      --)
        shift
        break
        ;;
      *)
        err "Unknown option: $1"
        usage
        exit 1
        ;;
    esac
  done
}

latest_version() {
  require_cmd curl
  local api_response tag
  log "Querying GitHub for latest release of $APP_REPO"
  api_response=$(curl -fsSL "https://api.github.com/repos/${APP_REPO}/releases/latest") || {
    err "Unable to query GitHub releases; specify --version or check connectivity."
    exit 1
  }
  tag=$(printf '%s' "$api_response" | grep -m1 '"tag_name"' | sed -E 's/.*"v?([0-9]+(\.[0-9]+)*)".*/\1/')
  if [ -z "$tag" ]; then
    err "Could not determine latest release from GitHub response."
    exit 1
  fi
  VERSION="$tag"
  log "Latest release resolved to version $VERSION"
}

normalize_paths() {
  if [ -n "$TARBALL_PATH" ]; then
    log "Resolving tarball path: $TARBALL_PATH"
    local resolved_tarball
    resolved_tarball=$(readlink -f "$TARBALL_PATH") || {
      err "Unable to resolve tarball path: $TARBALL_PATH"; exit 1; }
    TARBALL_PATH="$resolved_tarball"
    [ -f "$TARBALL_PATH" ] || { err "Tarball not found: $TARBALL_PATH"; exit 1; }
    log "Using tarball at $TARBALL_PATH"
  fi
  if [ -n "$WHEEL_PATH" ]; then
    log "Resolving wheel path: $WHEEL_PATH"
    local resolved_wheel
    resolved_wheel=$(readlink -f "$WHEEL_PATH") || {
      err "Unable to resolve wheel path: $WHEEL_PATH"; exit 1; }
    WHEEL_PATH="$resolved_wheel"
    [ -f "$WHEEL_PATH" ] || { err "Wheel not found: $WHEEL_PATH"; exit 1; }
    log "Using wheel at $WHEEL_PATH"
  fi
}

infer_version_from_artifacts() {
  if [ -z "$VERSION" ] && [ -n "$WHEEL_PATH" ]; then
    local base
    base=$(basename "$WHEEL_PATH")
    VERSION=$(printf '%s' "$base" | sed -E 's/postfix_blocker-([0-9]+(\.[0-9]+)*)-py3.*/\1/')
    if [ -n "$VERSION" ]; then
      log "Inferred version $VERSION from wheel filename"
    fi
  fi
  if [ -z "$VERSION" ] && [ -n "$TARBALL_PATH" ]; then
    local base
    base=$(basename "$TARBALL_PATH")
    VERSION=$(printf '%s' "$base" | sed -E 's/postfix_blocker-([0-9]+(\.[0-9]+)*).tar.gz/\1/')
    if [ -n "$VERSION" ]; then
      log "Inferred version $VERSION from tarball filename"
    fi
  fi
}

prompt_for_missing_inputs() {
  if [ -z "$DB_URL" ]; then
    if [ "$NON_INTERACTIVE" -eq 1 ]; then
      err "--db-url is required in non-interactive mode."
      exit 1
    fi
    log "Prompting operator for Db2 SQLAlchemy URL"
    printf 'Enter Db2 SQLAlchemy URL (e.g. ibm_db_sa://user:pass@host:50000/BLOCKER?currentSchema=CRISOP): '
    read -r DB_URL
    if [ -z "$DB_URL" ]; then
      err "Database URL must not be empty."
      exit 1
    fi
  fi

  if [ "$POSTFIX_MODE" = "configure" ] && [ "$NON_INTERACTIVE" -eq 0 ]; then
    printf 'About to update Postfix recipient restrictions using postconf. Continue? [y/N]: '
    read -r confirm
    case "$confirm" in
      [Yy]*) ;;
      *)
        warn "Skipping Postfix configuration per operator response."
        POSTFIX_MODE="skip"
        log "Postfix configuration disabled by operator"
        ;;
    esac
  fi
}

install_packages() {
  require_cmd dnf
  log "Preparing OS package repositories"
  if command -v subscription-manager >/dev/null 2>&1; then
    log "Ensuring CodeReady Builder repo is enabled"
    subscription-manager repos --enable "codeready-builder-for-rhel-9-$(/usr/bin/arch)-rpms" || true
  else
    if ! dnf repolist | grep -qE '^crb'; then
      log "Enabling CRB repository via dnf config-manager"
      dnf -y install dnf-plugins-core >/dev/null
      dnf config-manager --set-enabled crb || true
    fi
  fi

  log "Installing required packages via dnf (curl, tar, gzip, which, gcc, make, openssl-devel, libffi-devel, python3, python3-devel, python3-pip, nodejs, npm, policycoreutils-python-utils, postfix, postfix-pcre, shadow-utils, git)"
  if command -v dnf >/dev/null 2>&1; then
    dnf -y module reset nodejs >/dev/null 2>&1 || true
    dnf -y module enable nodejs:20 >/dev/null 2>&1 || true
  fi
  dnf -y install --allowerasing \
    curl \
    tar \
    gzip \
    which \
    gcc \
    make \
    openssl-devel \
    libffi-devel \
    python3 \
    python3-devel \
    python3-pip \
    nodejs \
    npm \
    policycoreutils-python-utils \
    postfix \
    postfix-pcre \
    shadow-utils \
    git >/dev/null
}

ensure_python() {
  PYTHON_BIN="$(command -v python3)"
  if [ -z "$PYTHON_BIN" ]; then
    err "python3 not found after package installation."
    exit 1
  fi
  log "Using Python interpreter: $PYTHON_BIN"
}

install_pm2() {
  if ! command -v npm >/dev/null 2>&1; then
    warn "npm not available; skipping PM2 installation"
    return
  fi
  if command -v pm2 >/dev/null 2>&1; then
    log "PM2 already installed"
    return
  fi
  log "Installing PM2 process manager"
  if ! npm install -g pm2 >/dev/null; then
    warn "Failed to install PM2 globally; frontend service may not start"
  fi
}

ensure_user_and_dirs() {
  log "Ensuring system user and directory layout"
  if ! id "$APP_USER" >/dev/null 2>&1; then
    log "Creating system user $APP_USER"
    useradd --system --home "$PREFIX" --shell /sbin/nologin "$APP_USER"
  fi

  install -d -m 0755 -o "$APP_USER" -g "$APP_USER" "$PREFIX"
  install -d -m 0755 -o "$APP_USER" -g "$APP_USER" "$PREFIX/app"
  install -d -m 0755 -o "$APP_USER" -g "$APP_USER" "$PREFIX/downloads"
  install -d -m 0755 -o "$APP_USER" -g "$APP_USER" "$PREFIX/run"
  install -d -m 0750 -o "$APP_USER" -g "$APP_USER" "$LOG_DIR"
  install -d -m 0770 -o root -g "$APP_USER" "$PID_DIR"
  log "Directory preparation complete"
}

check_db2_driver() {
  if [ "$SKIP_DB2_CHECK" -eq 1 ]; then
    log "Skipping Db2 driver validation (--skip-db2-driver-check)"
    return
  fi

  # Prefer the explicit CLI driver only when using Db2 URLs; otherwise skip
  local url="$DB_URL"
  if [ -z "$url" ]; then
    if resolve_db_url_for_test; then
      url="$DB_URL_FOR_TEST"
    fi
  fi

  if [ -n "$url" ] && ! printf '%s' "$url" | grep -qi 'ibm_db'; then
    log "Db2 driver validation skipped (database URL does not use ibm_db)."
    return
  fi

  local python_bin="$PREFIX/venv/bin/python"
  if [ ! -x "$python_bin" ]; then
    warn "Python virtual environment missing; skipping Db2 driver validation"
    return
  fi

  log "Validating Db2 Python driver availability"
  local py_cmd output status
  py_cmd=$'import sys, traceback\ntry:\n    import ibm_db\n    import ibm_db_dbi\nexcept Exception:\n    traceback.print_exc()\n    sys.exit(1)\n'
  output=$(run_as_app "$python_bin" -c "$py_cmd" 2>&1)
  status=$?
  if [ "$status" -eq 0 ]; then
    log "Db2 Python driver import succeeded"
  else
    warn "Db2 Python driver import failed (exit=${status}). Install the IBM CLI driver or rerun with --skip-db2-driver-check."
    printf >&2 '%s\n' "$output"
  fi
}


resolve_db_url_for_test() {
  local env_path="$PREFIX/.env"
  local env_db=""
  if [ -f "$env_path" ]; then
    env_db=$(grep -E '^BLOCKER_DB_URL=' "$env_path" | tail -n1 | cut -d '=' -f2-)
  fi

  if [ -n "$env_db" ] && [ "$FORCE" -eq 0 ]; then
    DB_URL_FOR_TEST="$env_db"
    return 0
  fi

  if [ -n "$DB_URL" ]; then
    DB_URL_FOR_TEST="$DB_URL"
    return 0
  fi

  if [ -n "$env_db" ]; then
    DB_URL_FOR_TEST="$env_db"
    return 0
  fi
  DB_URL_FOR_TEST=""
  return 1
}

test_database_connectivity() {
  if ! resolve_db_url_for_test; then
    log "Database URL not available; skipping connectivity test"
    return
  fi

  local python_bin="$PREFIX/venv/bin/python"
  if [ ! -x "$python_bin" ]; then
    warn "Python virtual environment missing; skipping database connectivity test"
    return
  fi

  log "Testing database connectivity"
  if run_as_app env BLOCKER_DB_URL="$DB_URL_FOR_TEST" "$python_bin" - <<'PYCODE'
import os
import sys

try:
    from sqlalchemy import create_engine
except Exception as exc:  # pragma: no cover - install script runtime guard
    print(f"Unable to import SQLAlchemy: {exc}", file=sys.stderr)
    sys.exit(2)

db_url = os.environ.get("BLOCKER_DB_URL")
if not db_url:
    print("BLOCKER_DB_URL not set in environment", file=sys.stderr)
    sys.exit(1)

try:
    engine = create_engine(db_url, pool_pre_ping=True)
except Exception as exc:
    print(f"Failed to create SQLAlchemy engine: {exc}", file=sys.stderr)
    sys.exit(3)

try:
    with engine.connect():
        pass  # connection established successfully
except Exception as exc:
    print(f"Failed to connect to database: {exc}", file=sys.stderr)
    sys.exit(4)

sys.exit(0)
PYCODE
  then
    log "Database connectivity check succeeded"
  else
    warn "Database connectivity check failed; unable to connect using the provided database parameters."
  fi
}

run_as_app() {
  log "Running as $APP_USER: $*"
  runuser -u "$APP_USER" -- "$@"
}

systemd_available() {
  command -v systemctl >/dev/null 2>&1 || return 1
  [ -d /run/systemd/system ] || return 1
  # systemctl must be able to talk to a running systemd instance
  if ! systemctl show --property=Version >/dev/null 2>&1; then
    return 1
  fi
  return 0
}

prepare_artifacts() {
  local download_dir="$PREFIX/downloads"
  local tag="v$VERSION"
  local tarball_url="https://github.com/${APP_REPO}/releases/download/${tag}/postfix_blocker-${VERSION}.tar.gz"
  local wheel_url="https://github.com/${APP_REPO}/releases/download/${tag}/postfix_blocker-${VERSION}-py3-none-any.whl"

  if [ -z "$TARBALL_PATH" ]; then
    log "Downloading source tarball $tarball_url"
    run_as_app curl -fSL "$tarball_url" -o "$download_dir/postfix_blocker-${VERSION}.tar.gz"
    TARBALL_PATH="$download_dir/postfix_blocker-${VERSION}.tar.gz"
  else
    log "Reusing provided tarball $TARBALL_PATH"
  fi

  if [ -z "$WHEEL_PATH" ]; then
    log "Downloading wheel $wheel_url"
    run_as_app curl -fSL "$wheel_url" -o "$download_dir/postfix_blocker-${VERSION}-py3-none-any.whl"
    WHEEL_PATH="$download_dir/postfix_blocker-${VERSION}-py3-none-any.whl"
  else
    log "Reusing provided wheel $WHEEL_PATH"
  fi
}

unpack_application() {
  local app_dir="$PREFIX/app"
  if [ -d "$app_dir" ]; then
    if [ "$FORCE" -eq 1 ]; then
      log "Removing existing application directory"
      rm -rf "$app_dir"
      install -d -m 0755 -o "$APP_USER" -g "$APP_USER" "$app_dir"
    else
      log "Cleaning existing application directory"
      rm -rf "$app_dir"/*
    fi
  fi
  log "Unpacking tarball $TARBALL_PATH into $app_dir"
  run_as_app tar -xzf "$TARBALL_PATH" --strip-components=1 -C "$app_dir"
}

create_virtualenv() {
  local venv_dir="$PREFIX/venv"
  if [ -d "$venv_dir" ] && [ "$FORCE" -eq 1 ]; then
    log "Removing existing virtualenv"
    rm -rf "$venv_dir"
  fi
  if [ ! -d "$venv_dir" ]; then
    log "Creating virtual environment at $venv_dir"
    run_as_app "$PYTHON_BIN" -m venv "$venv_dir"
  else
    log "Virtual environment already exists at $venv_dir"
  fi
  log "Upgrading pip/setuptools/wheel"
  run_as_app "$venv_dir/bin/pip" install --upgrade pip setuptools wheel >/dev/null
  log "Installing postfix-blocker $VERSION"
  run_as_app "$venv_dir/bin/pip" install "$WHEEL_PATH" gunicorn >/dev/null
  local req_base="$PREFIX/app/requirements-base.txt"
  local req_db2="$PREFIX/app/requirements-db2.txt"
  if [ -f "$req_base" ]; then
    log "Validating Python requirements (base)"
    run_as_app "$venv_dir/bin/pip" install --no-deps -r "$req_base" >/dev/null
  fi
  if [ -f "$req_db2" ]; then
    if run_as_app "$venv_dir/bin/pip" show ibm-db >/dev/null 2>&1; then
      log "DB2 driver packages already present"
    else
      log "Installing DB2 driver packages"
      if ! run_as_app "$venv_dir/bin/pip" install -r "$req_db2" >/dev/null; then
        warn "ibm-db installation failed. Install the IBM CLI driver and rerun with --skip-db2-driver-check if necessary."
      fi
    fi
  fi
}

setup_frontend() {
  local frontend_dir="$PREFIX/app/frontend"
  if [ ! -d "$frontend_dir" ]; then
    warn "Frontend directory not found at $frontend_dir; skipping frontend setup"
    return
  fi

  if ! command -v npm >/dev/null 2>&1; then
    warn "npm command not available; skipping frontend setup"
    return
  fi

  log "Installing frontend dependencies (npm ci)"
  if ! run_as_app bash -lc "cd '$frontend_dir' && npm ci"; then
    warn "npm ci failed; frontend service may not start until dependencies are installed"
  fi

  local proxy_host="$API_HOST"
  if [ -z "$proxy_host" ] || [ "$proxy_host" = "0.0.0.0" ] || [ "$proxy_host" = "::" ]; then
    proxy_host="127.0.0.1"
  fi
  local proxy_target="http://${proxy_host}:${API_PORT}"

  if [ -f "$frontend_dir/proxy.json" ] && [ ! -f "$frontend_dir/proxy.json.dist" ]; then
    cp "$frontend_dir/proxy.json" "$frontend_dir/proxy.json.dist"
  fi

  log "Writing frontend proxy.json (target=${proxy_target})"
  cat >"$frontend_dir/proxy.json" <<EOF_PROXY
{
  "/addresses": {
    "target": "${proxy_target}",
    "secure": false,
    "changeOrigin": true
  },
  "/logs": {
    "target": "${proxy_target}",
    "secure": false,
    "changeOrigin": true
  },
  "/test": {
    "target": "${proxy_target}",
    "secure": false,
    "changeOrigin": true
  }
}
EOF_PROXY
  chown "$APP_USER":"$APP_USER" "$frontend_dir/proxy.json"
  chmod 0644 "$frontend_dir/proxy.json"

  log "Configuring npm start script for frontend service"
  run_as_app env FRONTEND_DIR="$frontend_dir" PYTHON_BIN="$PYTHON_BIN" FRONTEND_HOST="$FRONTEND_HOST" FRONTEND_PORT="$FRONTEND_PORT" "$PYTHON_BIN" - <<'PYCODE'
import json
import os
import pathlib

frontend_dir = pathlib.Path(os.environ['FRONTEND_DIR'])
pkg_path = frontend_dir / 'package.json'
data = json.loads(pkg_path.read_text())
scripts = data.setdefault('scripts', {})

scripts['start'] = (
    'ng serve --host ${FRONTEND_HOST:-0.0.0.0} '
    '--port ${FRONTEND_PORT:-4200} --proxy-config proxy.json'
)

scripts.setdefault('start:install', scripts['start'])

pkg_path.write_text(json.dumps(data, indent=2) + "\n")
PYCODE

  chown "$APP_USER":"$APP_USER" "$frontend_dir/package.json"

  local pm2_config="$frontend_dir/pm2.config.cjs"
  log "Writing PM2 ecosystem config at $pm2_config"
  cat >"$pm2_config" <<'EOF_PM2'
module.exports = {
  apps: [
    {
      name: 'postfixblocker-frontend',
      cwd: __dirname,
      script: '/usr/bin/npm',
      args: 'run start',
      interpreter: 'none',
      env: {
        FRONTEND_HOST: process.env.FRONTEND_HOST || '0.0.0.0',
        FRONTEND_PORT: process.env.FRONTEND_PORT || '4200',
      },
    },
  ],
};
EOF_PM2
  chown "$APP_USER":"$APP_USER" "$pm2_config"
  chmod 0644 "$pm2_config"

  log "Frontend setup complete (host=${FRONTEND_HOST}, port=${FRONTEND_PORT})"
}

write_env_file() {
  local env_path="$PREFIX/.env"
  if [ -f "$env_path" ] && [ "$FORCE" -eq 0 ]; then
    log ".env exists; keeping existing file"
    return
  fi
  if [ -f "$env_path" ]; then
    log "Backing up existing .env"
    cp "$env_path" "$env_path.bak.$(date +%Y%m%d%H%M%S)"
  fi

  log "Writing environment file to $env_path"
  cat >"$env_path" <<EOF_ENV
BLOCKER_DB_URL=$DB_URL
BLOCKER_INTERVAL=5
POSTFIX_DIR=$POSTFIX_DIR
BLOCKER_PID_FILE=$PID_DIR/blocker.pid
API_HOST=$API_HOST
PORT=$API_PORT
API_LOG_FILE=$LOG_DIR/api.log
API_LOG_LEVEL=INFO
BLOCKER_LOG_FILE=$LOG_DIR/blocker.log
BLOCKER_LOG_LEVEL=INFO
FRONTEND_HOST=$FRONTEND_HOST
FRONTEND_PORT=$FRONTEND_PORT
EOF_ENV

  chown "$APP_USER":"$APP_USER" "$env_path"
  chmod 0640 "$env_path"
  log ".env written and permissions adjusted"
}

write_systemd_units() {
  if [ "$SYSTEMD_MODE" = "skip" ]; then
    log "Skipping systemd unit installation"
    return
  fi

  log "Rendering systemd unit files to /etc/systemd/system"
  cat >/etc/systemd/system/postfixblocker-blocker.service <<SERVICE_BLOCKER
[Unit]
Description=postfix-blocker refresh service
Requires=postfix.service
After=postfix.service network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
Group=root
EnvironmentFile=$PREFIX/.env
WorkingDirectory=$PREFIX
ExecStart=$PREFIX/venv/bin/postfix-blocker-blocker
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
SERVICE_BLOCKER

  cat >/etc/systemd/system/postfixblocker-api.service <<SERVICE_API
[Unit]
Description=postfix-blocker API (Flask via Gunicorn)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$APP_USER
Group=$APP_USER
Environment=IBM_DB_HOME=/opt/ibm/db2/current
EnvironmentFile=$PREFIX/.env
WorkingDirectory=$PREFIX
ExecStart=$PREFIX/venv/bin/gunicorn -w 2 -b ${API_HOST}:${API_PORT} postfix_blocker.api:app
Restart=on-failure
RestartSec=5s
StandardOutput=journal
StandardError=journal
SyslogIdentifier=postfixblocker-api

[Install]
WantedBy=multi-user.target
SERVICE_API

  cat >/etc/systemd/system/postfixblocker-frontend.service <<SERVICE_FRONTEND
[Unit]
Description=postfix-blocker Angular frontend dev server
After=postfixblocker-api.service network-online.target
Wants=postfixblocker-api.service

[Service]
Type=simple
User=$APP_USER
Group=$APP_USER
EnvironmentFile=$PREFIX/.env
WorkingDirectory=$PREFIX/app/frontend
ExecStart=/usr/local/bin/pm2-runtime start $PREFIX/app/frontend/pm2.config.cjs
-ExecStop=/usr/local/bin/pm2 delete postfixblocker-frontend || true
Restart=on-failure
RestartSec=5s
StandardOutput=journal
StandardError=journal
SyslogIdentifier=postfixblocker-frontend

[Install]
WantedBy=multi-user.target
SERVICE_FRONTEND

  chmod 0644 /etc/systemd/system/postfixblocker-*.service
  log "Systemd units available: postfixblocker-blocker.service, postfixblocker-api.service, postfixblocker-frontend.service"

  if [ "$SYSTEMD_MODE" = "enable" ]; then
    if systemd_available; then
      log "Reloading systemd daemon"
      if systemctl daemon-reload; then
        log "Enabling and starting postfixblocker-blocker"
        systemctl enable --now postfixblocker-blocker.service || warn "Failed to enable/start postfixblocker-blocker; inspect systemctl status"
        log "Enabling and starting postfixblocker-api"
        systemctl enable --now postfixblocker-api.service || warn "Failed to enable/start postfixblocker-api; inspect systemctl status"
        log "Enabling and starting postfixblocker-frontend"
        systemctl enable --now postfixblocker-frontend.service || warn "Failed to enable/start postfixblocker-frontend; inspect systemctl status"
      else
        warn "systemctl daemon-reload failed; wrote systemd units but skipped enable/start"
        warn "Re-run with --systemd-mode write-only to suppress this warning."
      fi
    else
      local pid1
      pid1=$(cat /proc/1/comm 2>/dev/null || echo "unknown")
      warn "systemd not active on this host (PID 1=$pid1); wrote units but skipped enable/start"
      warn "Re-run with --systemd-mode write-only to suppress this warning."
    fi
  else
    log "Systemd units written; operator must enable/start them manually."
  fi
}

configure_postfix() {
  if [ "$POSTFIX_MODE" = "skip" ]; then
    log "Skipping Postfix recipient restriction configuration"
    return
  fi
  if ! command -v postconf >/dev/null 2>&1; then
    warn "postconf not found; cannot configure Postfix automatically."
    return
  fi

  local restrictions="check_recipient_access hash:${POSTFIX_DIR}/blocked_recipients, check_recipient_access pcre:${POSTFIX_DIR}/blocked_recipients.pcre, warn_if_reject check_recipient_access hash:${POSTFIX_DIR}/blocked_recipients_test, warn_if_reject check_recipient_access pcre:${POSTFIX_DIR}/blocked_recipients_test.pcre, permit_mynetworks, reject_unauth_destination"

  log "Updating Postfix smtpd_recipient_restrictions"
  postconf -e "smtpd_recipient_restrictions = ${restrictions}"
  log "Postfix configuration updated"

  if command -v postfix >/dev/null 2>&1; then
    log "Reloading Postfix"
    postfix reload || warn "postfix reload reported a warning; inspect logs."
  fi
}

print_summary() {
  log "Printing installation summary"
  cat <<SUMMARY_BLOCK

postfix-blocker $VERSION installed at $PREFIX.

Next steps:
  - Review /etc/systemd/system/postfixblocker-*.service if systemd-mode != enable.
  - Verify Db2 connectivity and run sql/db2_init.sql if this is the first deployment.
  - Confirm Postfix restrictions in $POSTFIX_DIR/main.cf align with your policy.
  - Logs: $LOG_DIR, PID file directory: $PID_DIR
  - Frontend dev server listening on ${FRONTEND_HOST}:${FRONTEND_PORT} (access via http://<server-host>:${FRONTEND_PORT})
    (managed by PM2; config at $PREFIX/app/frontend/pm2.config.cjs)
SUMMARY_BLOCK
}

main() {
  parse_args "$@"
  require_root
  log "Starting postfix-blocker installer"
  if [ -n "$VERSION" ]; then
    log "Version requested via arguments: $VERSION"
  else
    log "No version specified; installer will determine latest release"
  fi
  normalize_paths
  infer_version_from_artifacts
  if [ -z "$VERSION" ]; then
    log "Determining latest release from remote metadata"
    latest_version
  fi
  log "Resolved installation version: $VERSION"
  log_configuration
  prompt_for_missing_inputs
  log "Installing prerequisite packages"
  install_packages
  ensure_python
  install_pm2
  log "Preparing application user and directories"
  ensure_user_and_dirs
  log "Ensuring release artifacts are available"
  prepare_artifacts
  log "Unpacking application payload"
  unpack_application
  log "Setting up Python virtual environment"
  create_virtualenv
  log "Setting up frontend application"
  setup_frontend
  check_db2_driver
  test_database_connectivity
  log "Writing application environment configuration"
  write_env_file
  log "Setting up systemd units"
  write_systemd_units
  log "Applying Postfix integration settings"
  configure_postfix
  print_summary
  log "Installer completed successfully"
}

main "$@"
