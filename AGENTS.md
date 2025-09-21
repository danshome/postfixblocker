# AGENTS.md

## Purpose & Scope
This file provides instructions and tips for agents working inside this project—covering workflow, Git usage, repository conventions, build/test requirements, architecture, and PR expectations.

**Scope rules**
- The scope of an `AGENTS.md` file is the entire directory tree rooted at the folder that contains it.
- For every file you touch, you must obey instructions in any `AGENTS.md` whose scope includes that file.
- Deeper (more-nested) `AGENTS.md` files take precedence on conflicts.
- Direct system/developer/user instructions in the prompt always take precedence over `AGENTS.md`.
- `AGENTS.md` files may appear anywhere (e.g., `/`, `~`, or within repos) and may include PR-message expectations.

If an `AGENTS.md` includes programmatic checks, you **must run them all** and make a best effort to ensure they pass **after** your changes—even if your change seems trivial (e.g., docs).

---

## Task Workflow (General)
- The user will provide a task.
- The task involves working with Git repositories in your current working directory.
- Run/terminate all terminal commands necessary for the task; do not finish until commands complete.

---

## Git & Commit Rules
- **Do not create new branches.**
- Use Git to commit your changes. **Do not modify or amend existing commits.**
- If pre-commit fails, **fix issues and retry**.
- Run `git status` and leave the worktree **clean** (no uncommitted changes).
- Only committed code will be evaluated.

**Pre-commit & autofix**
- Pre-commit is required before committing: `pre-commit run --all-files`  
  or run the fixer: `./scripts/precommit-fix.sh` (Ruff/ESLint fix, restage, run hooks).

**Commit messages**
- Subject: concise, imperative, ≤ 72 chars.  
- Include a body explaining “why” when non-trivial.

---

## Repository Guidelines — Critical Requirements
**You MUST:**
- Run `make ci` **before** changes and **after** any changes. If tests fail, **fix them**.
- Meet **code coverage** requirements.
- **Document all code changes**.
- Fix all **ERROR**, **WARN/WARNING**, and **FAIL** across:
  - ESLint (frontend), Ruff (Python), Bandit (security), and **all tests**.
- Ensure **no tests are skipped**. If a dependency (DB/SMTP) is unavailable, the test should **fail**, not skip.

**Special signal check**
- If there’s a line-count difference between `./logs/postfix_db2.maillog` and `./logs/postfix.maillog`, it signals tests that exercise only one Postfix instance. You **must** fix tests to cover **both**.  
  `make ci` will surface this with `[AI_SIGNAL][MAILLOG]`.

---

## Project Structure & Module Organization
- `postfix_blocker/` – Python services
  - `api.py` — thin entrypoint exposing Flask app via web/app_factory
  - `services/blocker_service.py` — blocker loop: writes Postfix maps and runs postmap/reload
  - `blocker.py` — thin runner to start blocker_service; no legacy re-exports (deprecation window noted below)
- `frontend/` – Angular 20 UI (Material, Karma, Playwright)
- `docker/` – Postfix image and supervisord config
- `tests/` – Pytest suites: unit, backend (DB), and e2e
- `logs/` – Host-mounted logs (`api.log`, `blocker.log`)
- `sql/` – SQL scripts for DBAs if manual migrations are needed

---

## Build, Test, and Development Commands
- **Unified build/test:** `make ci` (lint, build, unit/backend/e2e for Python + frontend)
- **Start stacks:** `docker compose up --build -d`
- **Python tests:** `pytest -q` (markers: `-m unit|backend|e2e`)
- **Frontend unit:**  
  ```bash
  cd frontend && npm install && npm test
  ```
- **Frontend e2e:**  
  ```bash
  cd frontend && npm run e2e   # requires Docker stack running
  ```
- **Dev server:**  
  ```bash
  cd frontend && npm run start 
  # or
  npm run start:db2
  ```
- **Lint/fix + hooks:** `./scripts/precommit-fix.sh` (Ruff/ESLint fix, restage, run hooks)

---

## Coding Style & Naming Conventions
**Python**
- Style: PEP 8, 4-space indent
- Format: `ruff format`
- Lint: `ruff check`
- Types: `mypy`
- Security: `bandit`
- Naming: `snake_case` (modules/functions), `PascalCase` (classes)

**TypeScript/Angular**
- ESLint with `@typescript-eslint`, `sonarjs`
- Naming: `camelCase` (vars/services), `PascalCase` (components)

---

## Testing Guidelines
- Pytest files: `tests/test_*.py`; keep **unit tests fast and deterministic**.
- **No skipped tests**—not even “graceful” skips. If DB or SMTP isn’t available, the test must **fail** (this replaces any earlier guidance suggesting graceful skips).
- Frontend: Karma for unit specs; Playwright for e2e; mock HTTP with `HttpTestingController`.
- Full sweep before PR:
  ```bash
  pytest -q && (cd frontend && npm test && npm run e2e)
  ```

---

## Security & Configuration Tips
- **Do not commit secrets**; use environment variables or Docker secrets.
- Logging (rotating files + console):
  - **API:** `API_LOG_LEVEL`, `API_LOG_FILE` → `./logs/api.log`
  - **Blocker:** `BLOCKER_LOG_LEVEL`, `BLOCKER_LOG_FILE` → `./logs/blocker.log`
- Postfix maps live in `/etc/postfix/*`; blocker writes and reloads automatically.
- API ↔ Blocker refresh IPC (same host/container):
  - Blocker writes a PID file and listens for `SIGUSR1` for immediate refresh.
  - API sends `SIGUSR1` to the PID from `BLOCKER_PID_FILE` after mutations.
  - Ensure both share the same `BLOCKER_PID_FILE` (default `/var/run/postfix-blocker/blocker.pid`).
  - If signaling fails, blocker still polls using a DB change marker at `BLOCKER_INTERVAL`.

---

## Backend Architecture: `postfix_blocker`
**Config**
- `postfix_blocker/config.py` — `Config` dataclass and `load_config()`. Centralizes env defaults (DB URL, intervals, paths, log-level defaults).

**Logging**
- `postfix_blocker/logging_setup.py` — common logging initialization and dynamic level updates (`configure_logging`, `set_logger_level`).
- `postfix_blocker/services/log_levels.py` — thin wrapper for runtime level changes.

**Database**
- `postfix_blocker/db/engine.py` — `get_engine()` factory using env config.
- `postfix_blocker/db/schema.py` — lazy SQLAlchemy metadata, `blocked_addresses`, `cris_props` tables + getters.
- `postfix_blocker/db/migrations.py` — `init_db(engine)` creates tables & applies lightweight migrations.
- `postfix_blocker/db/props.py` — property keys and `get_prop()/set_prop()` upsert logic.

**Domain models**
- `postfix_blocker/models/entries.py` — `BlockEntry` dataclass and row↔dict converters.

**Postfix integration**
- `postfix_blocker/postfix/maps.py` — `write_map_files(entries, postfix_dir=None)` writes maps for enforce/test (literal & regex).
- `postfix_blocker/postfix/control.py` — `reload_postfix()`, `has_postfix_pcre()`; runs `postmap`/`postfix reload` with tolerant logging.
- `postfix_blocker/postfix/log_level.py` — `apply_postfix_log_level(level)`, `resolve_mail_log_path()` mapping UI levels to `debug_peer_level` & resolving maillog path.

**Services**
- `postfix_blocker/services/blocker_service.py` — long-running monitor, reads DB entries, writes Postfix maps, reloads Postfix, watches dynamic log level.
- `postfix_blocker/services/log_tail.py` — `tail_file(path, lines)` deterministic tail for API responses.

**Web API**
- `postfix_blocker/web/app_factory.py` — `create_app()` Flask app factory; logging hooks; lazy DB readiness; registers blueprints.
- `postfix_blocker/web/routes_addresses.py` — `/addresses` CRUD.
- `postfix_blocker/web/routes_logs.py` — `/logs/level/<service>`, `/logs/refresh/<name>`, `/logs/tail`.
- Run via:
  - Dev: `python -m postfix_blocker.web`
  - Prod: `gunicorn postfix_blocker.api:app`
- `postfix_blocker/api.py` — thin entrypoint delegating to the app factory.

**Legacy entrypoint (deprecation window)**
- `postfix_blocker/blocker.py` — thin runner for blocker service with deprecation warnings and back-compat shims (POSTFIX_DIR, BlockEntry, write_map_files, helper re-exports). Plan to remove re-exports after a deprecation window (see `REFactor_STATUS.md`).

---

## Adding Features
- **DB-backed features:** define tables in `db/schema.py`, add migrations in `db/migrations.py`, expose helpers in `services/*`, surface via a new `web/routes_*.py` blueprint.
- **Logging:** prefer `logging_setup.configure_logging()`; for dynamic changes, use `services/log_levels.set_level()`.
- **Postfix ops:** use `postfix/*` modules. Do **not** shell out directly from routes; keep commands in `postfix/control.py`.

---

## Pull Request Guidelines
PRs must include:
- What/why, linked issues, and screenshots/GIFs for UI changes.
- **Passing** Python + frontend tests and **green** pre-commit.
- Updated docs (README/INSTALL/CHANGELOG) when behavior or config changes.

---

## Citations (when you browse files or run terminal commands)
When your response references repository files or terminal output, include citations in your **final response** (not in the PR message body):

1) **File path citation**
```
【F:<file_path>†L<line_start>(-L<line_end>)?】
```
- `file_path` is the exact path **relative to the repo root** containing the relevant text.

2) **Terminal output citation**
```
【<chunk_id>†L<line_start>(-L<line_end>)?】
```
- Use terminal citations for relevant command outputs (e.g., test results).  
- Do not cite empty lines; ensure line numbers are correct.  
- Prefer file citations unless terminal output is directly relevant (e.g., test failure lines).  
- Do **not** cite previous PR diffs/comments or use Git hashes as chunk IDs.

**Typical usage**
- For PR creation tasks, use **file citations** when summarizing code/documentation changes, and **terminal citations** when summarizing test/lint results.

---

## Conflict Resolution Notes
- Where earlier guidance suggested backend/e2e tests may “skip gracefully” if DB is unavailable, this is superseded by the **CRUCIAL** rule: **tests must never skip**. If infrastructure is unavailable, tests **fail** and must be fixed or the environment prepared.
- If conflicting style/naming rules appear, apply the more deeply nested `AGENTS.md` in the directory tree for the files you are editing. Otherwise, default to the stricter rule spelled out above.

---

## Final Checklist (before you finish)
1. Run `make ci` (fix anything red).  
2. Ensure **no skipped tests**, adequate coverage, and **no** lint/Bandit warnings/errors.  
3. Run pre-commit (`pre-commit run --all-files` or `./scripts/precommit-fix.sh`).  
4. Confirm worktree is clean: `git status`.  
5. Ensure code changes are **documented**; update READMEs/INSTALL/CHANGELOG if behavior/config changed.  
6. Commit changes (no amend/rebase), push as required, and prepare a PR with the required sections.

--- 

*End of merged AGENTS.md.*
