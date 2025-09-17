# Repository Guidelines

**ALWAYS** run `make ci` before changes, and after any changes.

## Project Structure & Module Organization
- `postfix_blocker/` – Python services
  - `api.py` (thin entrypoint exposing Flask app via web/app_factory)
  - `services/blocker_service.py` (blocker loop: writes Postfix maps and runs postmap/reload)
  - `blocker.py` (thin runner to start blocker_service; no legacy re-exports)
- `frontend/` – Angular 20 UI (Material, Karma, Playwright)
- `docker/` – Postfix image and supervisord config
- `tests/` – Pytest suites: unit, backend (DB), and e2e
- `logs/` – Host‑mounted logs (`api.log`, `blocker.log`)

## Build, Test, and Development Commands
- Unified build/test: `make ci` (lint, build, unit/backend/e2e for Python + frontend)
- Start stacks: `docker compose up --build -d`
- Python tests: `pytest -q` (markers: `-m unit|backend|e2e`)
- Frontend unit: `cd frontend && npm install && npm test`
- Frontend e2e: `cd frontend && npm run e2e` (Docker stack running)
- Dev server: `cd frontend && npm run start` (PG) or `npm run start:db2`
- Lint/fix + hooks: `./scripts/precommit-fix.sh` (Ruff/ESLint fix, restage, run hooks)

## Coding Style & Naming Conventions
- Python: PEP 8, 4‑space indent
  - Format: `ruff format`; Lint: `ruff check`; Types: `mypy`; Security: `bandit`
- TypeScript: ESLint (`@typescript-eslint`, `sonarjs`) per Angular style guide
- Naming: Python `snake_case` (modules/functions), `PascalCase` (classes); TS `camelCase` (vars/services), `PascalCase` (components)

## Testing Guidelines
- Pytest files: `tests/test_*.py`; keep unit tests fast and deterministic
- Backend/e2e tests skip gracefully if DB is unavailable; use explicit markers
- Frontend: Karma for unit specs; Playwright for e2e; mock HTTP with `HttpTestingController`
- Full sweep before PR: `pytest -q && (cd frontend && npm test && npm run e2e)`

## Commit & Pull Request Guidelines
- Commits: concise, imperative subject (≤72 chars); body explains “why” when non‑trivial
- Pre‑commit is required before committing: `pre-commit run --all-files` (or `./scripts/precommit-fix.sh`)
- PRs should include:
  - What/why, linked issues, screenshots/GIFs for UI changes
  - Passing Python + frontend tests and green pre‑commit
  - Updated docs (README/INSTALL/CHANGELOG) when behavior or config changes

## Security & Configuration Tips
- Do not commit secrets; use environment variables/Docker secrets
- Logging (rotating files + console):
  - API: `API_LOG_LEVEL`, `API_LOG_FILE` → `./logs/api.log`
  - Blocker: `BLOCKER_LOG_LEVEL`, `BLOCKER_LOG_FILE` → `./logs/blocker.log`
- Postfix maps live in `/etc/postfix/*`; blocker writes and reloads automatically
- API ↔ Blocker refresh IPC (same host/container):
  - Blocker writes a PID file and listens for `SIGUSR1` to trigger an immediate refresh.
  - API sends `SIGUSR1` to the PID read from `BLOCKER_PID_FILE` after mutations.
  - Ensure both processes share the same `BLOCKER_PID_FILE` path (default `/var/run/postfix-blocker/blocker.pid`).
  - If signaling fails, blocker still polls using a DB change marker at `BLOCKER_INTERVAL`.



## Backend architecture: postfix_blocker

The backend is organized into focused modules with thin entrypoints. Use these when extending the system:

- config
  - `postfix_blocker/config.py`: `Config` dataclass and `load_config()`. Centralizes env defaults (DB URL, intervals, paths, log-level defaults).

- logging
  - `postfix_blocker/logging_setup.py`: common logging initialization and dynamic level updates (`configure_logging`, `set_logger_level`).
  - `postfix_blocker/services/log_levels.py`: thin wrapper for runtime level changes.

- database
  - `postfix_blocker/db/engine.py`: `get_engine()` — SQLAlchemy engine factory using env configuration.
  - `postfix_blocker/db/schema.py`: lazy SQLAlchemy metadata and `blocked_addresses`, `cris_props` table definitions with getters.
  - `postfix_blocker/db/migrations.py`: `init_db(engine)` — create tables and apply lightweight migrations.
  - `postfix_blocker/db/props.py`: property keys and `get_prop()/set_prop()` upsert logic.

- domain models
  - `postfix_blocker/models/entries.py`: `BlockEntry` dataclass and row<->dict converters.

- Postfix integration
  - `postfix_blocker/postfix/maps.py`: `write_map_files(entries, postfix_dir=None)` — writes maps for enforce/test (literal and regex).
  - `postfix_blocker/postfix/control.py`: `reload_postfix()`, `has_postfix_pcre()` — runs `postmap` and `postfix reload` with tolerant logging.
  - `postfix_blocker/postfix/log_level.py`: `apply_postfix_log_level(level)`, `resolve_mail_log_path()` — maps UI levels to `debug_peer_level` and resolves mail log path.

- services
  - `postfix_blocker/services/blocker_service.py`: long-running monitor loop that reads DB entries, writes Postfix maps, reloads Postfix, and watches dynamic log level.
  - `postfix_blocker/services/log_tail.py`: `tail_file(path, lines)` — deterministic tail for API responses.

- web API
  - `postfix_blocker/web/app_factory.py`: `create_app()` — Flask app factory; installs logging hooks, keeps lazy DB readiness, registers blueprints.
  - `postfix_blocker/web/routes_addresses.py`: `/addresses` CRUD endpoints.
  - `postfix_blocker/web/routes_logs.py`: `/logs/level/<service>`, `/logs/refresh/<name>`, `/logs/tail` endpoints.
  - Run via `python -m postfix_blocker.web` (dev) or `gunicorn postfix_blocker.api:app` (prod). `postfix_blocker/api.py` is a thin entrypoint that delegates to the app factory.

- legacy entrypoint (deprecation window)
  - `postfix_blocker/blocker.py`: thin runner for the blocker service with deprecation warnings and back-compat shims (POSTFIX_DIR, BlockEntry, write_map_files, helper re-exports). Plan to remove re-exports after a deprecation window (see REFactor_STATUS.md).

Adding features
- DB-backed features: define tables in `db/schema.py`, add migrations in `db/migrations.py`, expose helpers in `services/*`, and surface via a new `web/routes_*.py` blueprint.
- Logging: prefer `logging_setup.configure_logging()`; for dynamic changes, use `services/log_levels.set_level()`.
- Postfix ops: use `postfix/*` modules. Do not shell out directly from routes; keep commands in `postfix/control.py`.
