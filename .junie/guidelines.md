# Repository Guidelines

> MANDATORY: All agents MUST run `make ci` as the final step for every change—no matter how small. If `make ci` reports any issues (lint, type, build, tests, coverage, mutation, or packaging), the agent MUST fix them before submitting or merging.

## Project Structure & Module Organization
- `postfix_blocker/` holds the Flask API, blocker service loop, and Postfix helpers. Key modules: `web/app_factory.py` (app wiring), `services/blocker_service.py` (refresh loop), and `postfix/` (maps, reload, log level integration).
- `frontend/` contains the Angular 20 UI with Material components, Karma specs under `src/app`, and Playwright e2e specs in `e2e/`.
- `tests/` aggregates pytest unit, backend (DB), and e2e suites. Host-mounted logs live in `logs/`; Docker assets are in `docker/`.

## Build, Test, and Development Commands
Core CI/Dev
- `make ci` — Lint, build, and run all tests (Python unit+backend+e2e, frontend unit+e2e).
- `make init` — Create virtualenv and install backend+frontend dependencies.
- `make install` — Install backend+frontend dependencies.
- `make install-python` — Install Python dependencies into venv.
- `make install-frontend` — Install frontend dependencies (`npm ci`).

Lint/Format
- `make lint` — Ruff + mypy + bandit + ESLint (applies safe fixes).
- `make lint-python` — Ruff format+check, mypy, bandit.
- `make lint-frontend` — ESLint `--fix`.
- `make format` — Run all formatters (ruff + ESLint `--fix`).
- `make format-python` — Ruff format + fix.
- `make format-frontend` — ESLint `--fix`.

Build
- `make build` — Build the frontend.
- `make build-frontend` — Build the Angular app.

Tests (Python)
- `make test` — Python unit + frontend unit.
- `make test-python-all` — Unit + backend + e2e with coverage.
- `make test-python-unit` — Run `pytest -m unit`.
- `make test-python-backend` — Run `pytest -m backend` (starts docker compose).
- `make test-python-e2e` — Run `pytest -m e2e` (starts docker compose).

Tests (Frontend)
- `make test-frontend` — Karma unit tests in CI mode with coverage thresholds.
- `make test-frontend-e2e` — Playwright E2E tests (installs browsers; brings up docker stack).

End-to-end
- `make e2e` — Compose up, then backend E2E + Python E2E + frontend E2E.

Docker
- `make compose-up` — `docker compose up --build -d`.
- `make compose-down` — `docker compose stop`.
- `make compose-down-hard` — `docker compose down -v --remove-orphans`.
- `make docker-rebuild` — `docker compose build --no-cache`.
- `make docker-reset-all` — Down -v, rebuild no-cache, up with recreate.
- `make docker-reset-svc SERVICE=name` — Reset and recreate a single service.

Housekeeping
- `make hooks-update` — `pre-commit autoupdate` to refresh hook pins.
- `make clean-venv` — Remove `./venv`.
- `make clean-frontend` — Remove `frontend/node_modules`, `frontend/dist`, `frontend/.angular`, `frontend/test-results`.
- `make clean-logs` — Remove files under `./logs`.

Packaging/Release
- `make version` — Print computed version via `setuptools_scm`.
- `make dist` — Build sdist+wheel.
- `make dist-clean` — Remove `dist/`, `build/`, and egg-info.
- `make check-dist` — `twine check dist/*`.
- `make release` — Full CI, bump version (via `BUMP`), tag, push, build artifacts, optional GitHub release.
- `make publish-pypi` — Upload `dist/*` to PyPI via twine.
- `make changelog` — Generate `CHANGELOG.md`.

Mutation testing
- `make mutation-test-python` — Run mutmut and generate report; fails if survival > `MUT_SURVIVAL_MAX`%.
- `make mutation-report-python` — Summarize results and enforce threshold.
- `make mutation-test-frontend` — Stryker.js mutation tests for Angular.
- `make mutation-test-frontend-force` — Stryker.js ignoring initial test failures (troubleshooting).
- `make mutation-test` — Run both Python and frontend mutation tests.
- `make mutation-test-ci` — Conditional mutation tests in CI (toggle with `MUTATION_IN_CI`=1/0).

## Coding Style & Naming Conventions
- Python: PEP 8, 4-space indent, `ruff format` for formatting, `ruff check` and `mypy` enforced pre-commit, `bandit` for security scans. Use `snake_case` for functions/modules and `PascalCase` for classes.
- TypeScript: ESLint with flat config format, using `@typescript-eslint`(strictTypeChecked and stylisticTypeChecked presets), `sonarjs` for code smells, `unicorn` for idiomatic patterns, `jsdoc` for enforced documentation, `promise` for async handling, `security` for vulnerability detection, and Prettier integration for consistent formatting. Additional rules include explicit function return types, no floating promises, import ordering, complexity caps (e.g., max 15), max params (4), max lines per function (50), no console in prod code, prefer const, and comprehensive JSDoc requirements. Prefer `camelCase` for variables/services, `PascalCase` for components, and keep Angular templates declarative.
- You MUST Generate Frontend code that fully complies with all ESLint rules and configurations as defined in `frontend/eslint.config.mjs`. Under no circumstances are agents allowed to modify, disable, ignore, or alter any linting rules or configurations. Agents may not use ESLint directives (e.g., `/* eslint-disable */` or `// eslint-disable-next-line`) to bypass fixing code problems unless the issue genuinely cannot be resolved without breaking core functionality or introducing bugs—in such rare cases, the directive must be narrowly scoped (e.g., to a single line), accompanied by a detailed comment explaining why the rule cannot be followed and what alternatives were considered, and flagged for review in the commit/PR notes. All generated code must pass `npm run lint` without unresolved errors or warnings—fix issues directly in the code whenever possible to ensure high-quality, maintainable output. Violations of this policy, including unjustified use of directives, will result in rejected contributions.
- You MUST Generate Python code that fully complies with all Linting rules and configurations as defined in `pyproject.toml`. Under no circumstances are agents allowed to modify, disable, ignore, or alter any linting rules or configurations. Agents may not use directives (e.g., `# noqa:` or `# nosec:`) to bypass fixing code problems unless the issue genuinely cannot be resolved without breaking core functionality or introducing bugs—in such rare cases, the directive must be narrowly scoped (e.g., to a single line), accompanied by a detailed comment explaining why the rule cannot be followed and what alternatives were considered, and flagged for review in the commit/PR notes. All generated code must pass `make lint-python` without unresolved errors or warnings—fix issues directly in the code whenever possible to ensure high-quality, maintainable output. Violations of this policy, including unjustified use of directives, will result in rejected contributions.

## Testing Guidelines
- Name Python tests `tests/test_*.py`; keep unit tests deterministic and isolated. Ensure coverage stays within the existing >90% thresholds reported by `make ci`.
- Do not skip tests—if dependencies such as DB2 or MailHog are unavailable, fix the environment so failures surface.

## Code Coverage Requirements
For details on implementation (e.g., examples, tool configs, exclusions), see `tests/README.md`.
- **Minimum Thresholds**: Achieve ≥90% coverage across statements, branches, functions, and lines for all modules via `make ci`. Critical modules (e.g., security or high-risk logic) require ≥95% branch coverage, with 100% for critical paths.
- **Prioritize Meaningful Tests**: Focus on behavior, edge cases, and assertions over raw metrics; use branch coverage to test all decision points.
- **Enforce in CI/CD**: Integrate thresholds into pipelines (e.g., GitHub Actions) to fail builds on drops; pair with code reviews, static analysis (ruff, bandit), and mutation testing.
- **Refactor for Testability**: Extract complex logic (e.g., from large components like `AppComponent`) into testable units to meet goals efficiently.
- **Handle Gaps and Untestable Code**: Regularly review reports to address untested areas; exclude low-risk code (e.g., third-party libs or environment-specific branches) with documentation to avoid inflated or inaccurate metrics. Example: The DB2-only DDL/maintenance branch in `postfix_blocker/db/migrations.py` is excluded from unit-test coverage via `.coveragerc` because it cannot be exercised reliably without a real DB2 backend; integration/e2e tests are expected to cover it where feasible.
- **Avoid Gaming the System**:
  - **No Trivial Tests**: Prohibit tests for empty/trivial code lacking meaningful assertions.
  - **Behavior Over Metrics**: Validate requirements and edges, not just lines (e.g., failure conditions in services).
  - **Mutation Testing**: Use tools like mutmut to detect weak tests and superficial gains.

## Commit & Pull Request Guidelines
- Use imperative, ≤72-char commit subjects with explanatory bodies when changes are non-trivial. Stage only project-related edits.
- PRs should document what changed and why, link tracking issues, and include UI screenshots or GIFs when Angular views change.
- Present green `make ci` and `pre-commit run --all-files` output in the PR description; note any follow-up work explicitly.

## Security & Configuration Tips
- Never commit secrets; configure via environment variables or Docker secrets. Logging defaults route to `./logs/api.log` and `./logs/blocker.log`—keep those paths consistent across containers.
- Postfix refresh relies on the blocker writing maps and signaling via `SIGUSR1`; verify both API and blocker share the `BLOCKER_PID_FILE` path before releasing features.
