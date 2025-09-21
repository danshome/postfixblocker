# Repository Guidelines

## Project Structure & Module Organization
- `postfix_blocker/` holds the Flask API, blocker service loop, and Postfix helpers. Key modules: `web/app_factory.py` (app wiring), `services/blocker_service.py` (refresh loop), and `postfix/` (maps, reload, log level integration).
- `frontend/` contains the Angular 20 UI with Material components, Karma specs under `src/app`, and Playwright e2e specs in `e2e/`.
- `tests/` aggregates pytest unit, backend (DB), and e2e suites. Host-mounted logs live in `logs/`; Docker assets are in `docker/`.

## Build, Test, and Development Commands
- `make ci` — full lint, build, and test sweep; run before starting changes and again before committing.
- `pytest -q` — quick Python pass; add `-m unit|backend|e2e` to scope runs.
- `cd frontend && npm test` — Karma unit specs. `npm run e2e` exercises Playwright flows (requires `docker compose up --build -d`).
- `./scripts/precommit-fix.sh` — auto-format via Ruff/ESLint and executes pre-commit hooks.

## Coding Style & Naming Conventions
- Python: PEP 8, 4-space indent, `ruff format` for formatting, `ruff check` and `mypy` enforced pre-commit, `bandit` for security scans. Use `snake_case` for functions/modules and `PascalCase` for classes.
- TypeScript: ESLint with `@typescript-eslint` and `sonarjs` rules. Prefer `camelCase` for variables/services, `PascalCase` for components, and keep Angular templates declarative.

## Testing Guidelines
- Name Python tests `tests/test_*.py`; keep unit tests deterministic and isolated. Ensure coverage stays within the existing >95% thresholds reported by `make ci`.
- Do not skip tests—if dependencies such as DB2 or MailHog are unavailable, fix the environment so failures surface.
- For log-processing features, confirm both `logs/postfix.maillog` and `logs/postfix_db2.maillog` gain entries to satisfy the dual-postfix signal check.

## Commit & Pull Request Guidelines
- Use imperative, ≤72-char commit subjects with explanatory bodies when changes are non-trivial. Stage only project-related edits.
- PRs should document what changed and why, link tracking issues, and include UI screenshots or GIFs when Angular views change.
- Present green `make ci` and `pre-commit run --all-files` output in the PR description; note any follow-up work explicitly.

## Security & Configuration Tips
- Never commit secrets; configure via environment variables or Docker secrets. Logging defaults route to `./logs/api.log` and `./logs/blocker.log`—keep those paths consistent across containers.
- Postfix refresh relies on the blocker writing maps and signaling via `SIGUSR1`; verify both API and blocker share the `BLOCKER_PID_FILE` path before releasing features.
