# Repository Guidelines

## Project Structure & Module Organization
- `postfix_blocker/` – Python services
  - `api.py` (Flask REST API for managing the block list)
  - `blocker.py` (writes Postfix maps, runs postmap/reload)
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
