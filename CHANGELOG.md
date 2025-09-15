<!-- Updated to best practices on 2025-09-14; Keep a Changelog header added. -->
# Changelog

<!-- BEGIN GENERATED: CHANGELOG:HEADER -->
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog], and this project adheres to
[Semantic Versioning].

## [Unreleased]
### Added
- TODO: Add new features here.

### Changed
- TODO: Document changes here.

### Fixed
- TODO: List fixes here.

[Keep a Changelog]: https://keepachangelog.com/en/1.1.0/
[Semantic Versioning]: https://semver.org/spec/v2.0.0.html

<!-- END GENERATED: CHANGELOG:HEADER -->

## 2025-09-13 00:00 UTC

- Add IBM DB2 11.5 Docker service in `docker-compose.yml`.
- Make `postfix_blocker/blocker.py` backend-agnostic (DB2 + PostgreSQL):
  - Declare index via SQLAlchemy; remove backend-specific `CREATE INDEX IF NOT EXISTS`.
  - Export `get_blocked_table()` and publish `blocked_table` after initialization.
- Update `postfix_blocker/api.py` to fetch the table via `get_blocked_table()` at runtime.
- Update backend tests to document valid DB2 URLs.
- Add DB2 drivers to `requirements.txt` (`ibm-db`, `ibm-db-sa`).

## 2025-09-13 00:20 UTC

- Compose: add `postfix_db2` service (SMTP 1026, API 5002) to run Postfix with DB2 alongside Postgres.
- Backend tests: parameterize to exercise both Postgres and DB2 in one pytest run by default; skip if unavailable.
- E2E tests: add `tests/test_e2e.py` to run a minimal end-to-end scenario against both backends in one run; no manual config needed.
- README: document dual Postfix services, E2E running, and default ports.

## 2025-09-13 00:40 UTC

- Testing best practices: added pytest markers (unit/backend/e2e) via `pytest.ini`.
- Added DB/SMPP readiness helpers in `tests/utils_wait.py` and integrated into backend and e2e tests to reduce initial skips.
- Added `tests/test_e2e.py` e2e test harness to exercise both backends in one run with readiness waits.
- CI: Added GitHub Actions workflow `.github/workflows/ci.yml` with separate unit, backend, and e2e jobs.

## 2025-09-13 11:45 UTC

- Docker: Split Python dependencies into `requirements-base.txt` and `requirements-db2.txt`.
- Dockerfile: Make DB2 dependencies optional via `ENABLE_DB2` build arg to avoid build failures on arm64.
- Compose: Set `platform: linux/amd64` for postfix services; enable DB2 deps only for `postfix_db2`.
- Docs: Update README about conditional DB2 deps and platform notes.
- Verified: Brought up `db`, `mailhog`, and `postfix` services and validated E2E demo for PostgreSQL.

## 2025-09-14 04:55 UTC

- Tests: Fix E2E to avoid SQLAlchemy connect_args incompatible with DB2; add optional debug logging.
- Backend: Adjust postfix_blocker/blocker.py to avoid duplicate index creation and DB2 warnings; simplify schema.
- Docker: Rebuild postfix images to include latest app code; confirmed DB2 stack works end-to-end.
- Local runs: Execute tests from host against exposed ports; no tests copied into DB containers.

## 2025-09-14 09:00 UTC

- DevContainer: Add `.devcontainer/devcontainer.json` using a universal image with Python + Node, forwarded ports, and VS Code extension recommendations. Installs Python base deps and frontend npm packages on create.
- Frontend unit tests: Add Jest setup (`jest.config.js`, `setup-jest.ts`, `tsconfig.spec.json`) and unit tests for `AppComponent` using `HttpClientTestingModule`.
- Frontend e2e: Add Playwright config and e2e test covering add/list/delete. Start Angular dev server automatically and proxy API calls via `frontend/proxy.conf.json`.
- Docs: Update README with Jest/Playwright instructions.

## 2025-09-14 09:20 UTC

- Frontend DevContainer: Add `frontend/.devcontainer/devcontainer.json` using Playwright image for Node + browsers.
- Networking: Add `--add-host=host.docker.internal:host-gateway` to reach host services from container.
- Proxy: Add `frontend/proxy.devcontainer.json` to forward API calls to `http://host.docker.internal:5001`.
- Scripts: Add `start:devc` in `frontend/package.json` to run dev server with the DevContainer proxy.
- Docs: README section describing how to use the frontend DevContainer.

## 2025-09-14 09:35 UTC

- Root DevContainer (UI-only): Replace root `.devcontainer/devcontainer.json` with a Playwright-based Node environment that auto-starts the Angular dev server on container start and forwards port 4200. Adds host gateway mapping for proxying API calls to the host.
- Docs: Update README to document both the root UI DevContainer (auto-start) and the frontend-only DevContainer.

## 2025-09-14 09:45 UTC

- DevContainer status check: Add `.devcontainer/scripts/wait-for-port.sh` and update root DevContainer to wait for `http://localhost:4200` before marking the container ready.

## 2025-09-14 10:05 UTC

- Frontend: Upgrade Angular packages to `^20.0.0` and switch the CLI builder to `@angular-devkit/build-angular:application`.
- Frontend: Update `rxjs` to `^7.8.x` (Angular 20 peer range) and `zone.js` to `^0.15.0`.
- Tooling: Bump `@angular/cli` to `^20.0.0` and `typescript` to `^5.6.0`.

## 2025-09-14 10:20 UTC

- Unit tests: Switch to Karma + Jasmine for Angular 20 to resolve Jest preset incompatibilities; add `karma.conf.js` and `src/test.ts`, configure `angular.json:test` target.
- Dependencies: Remove Jest-related dev deps; add Karma/Jasmine dev deps and `@angular-devkit/build-angular`.

## 2025-09-14 10:35 UTC

- Docs: Update `AGENTS.md` with a Codex AI agent frontend-change checklist including clean install, unit tests, and e2e steps.

## 2025-09-14 10:58 UTC

- Repo hygiene: Add `.angular/` to `.gitignore` to avoid committing Angular workspace cache/config artifacts.

## 2025-09-14 11:02 UTC

- Repo hygiene: Re-add `.angular/` to `.gitignore` after accidental overwrite.

## 2025-09-14 11:08 UTC

- Repo hygiene: Update root `.gitignore` to ignore `frontend/.angular/` explicitly (Angular workspace cache inside the frontend app).

## 2025-09-14 11:15 UTC

- Frontend: Migrate to standalone bootstrap for Angular 20.
  - `AppComponent` marked `standalone: true` with `CommonModule` and `FormsModule` imports.
  - `main.ts` uses `bootstrapApplication(AppComponent)` with `provideHttpClient()`.
  - `angular.json` build target switched to `@angular-devkit/build-angular:application`.
- Tests: Update `app.component.spec.ts` to import standalone `AppComponent` + `HttpClientTestingModule`; unit tests pass under Karma/ChromeHeadless.

## 2025-09-14 11:20 UTC

- Frontend: Remove deprecated `defaultProject` from `frontend/angular.json` to silence Angular CLI workspace warning.
- Frontend: Set `target: ES2022` and `useDefineForClassFields: false` in `frontend/tsconfig.json` to match Angular CLI defaults and remove the TS warning.

## 2025-09-14 11:26 UTC

- Frontend tests: Eliminate noisy "Some of your tests did a full page reload!" by running Karma in non-watch mode and simplifying reporters.
  - `frontend/package.json`: `npm test` now runs `ng test --watch=false`.
  - `frontend/karma.conf.js`: remove HTML reporter and set `autoWatch: false`.
  - `frontend/src/test.ts`: guard against beforeunload noise.

## 2025-09-14 11:30 UTC

- Frontend e2e: Fix Playwright webServer startup by updating Angular dev-server config to use `buildTarget` instead of deprecated `browserTarget` in `frontend/angular.json`.

## 2025-09-14 11:34 UTC

- Frontend build: Update Angular 20 application builder config to use `browser: "src/main.ts"` instead of deprecated `main`. Remove unused `polyfills` in build options. This resolves dev-server schema validation errors when starting Playwright's webServer.

## 2025-09-14 11:40 UTC

- Frontend e2e: Ensure API proxy is active during `ng serve` by adding `proxyConfig: "proxy.conf.json"` to the `serve` target in `frontend/angular.json`. This fixes 404s for `/addresses` during Playwright runs.

## 2025-09-14 11:48 UTC

- API resilience: Make `postfix_blocker/api.py` lazily initialize the database and return 503 `{"error": "database not ready"}` when the backend is unavailable (e.g., DB2 startup). This prevents the API process from crashing so the dev proxy no longer shows ECONNRESET and the UI can stay responsive.

## 2025-09-14 11:55 UTC

- Frontend e2e (DB2): Add `frontend/playwright.db2.config.ts` and npm scripts `e2e:db2` and `e2e:db2:ui` to run the e2e suite against the DB2-backed API via `npm run start:db2`.

## 2025-09-14 12:05 UTC

- Frontend e2e matrix: Update `frontend/playwright.config.ts` to run a two-project matrix:
  - `pg-chromium` using `npm run start` on port 4200 (Postgres API).
  - `db2-chromium` using `npm run start:db2 -- --port 4201` on port 4201 (DB2 API).
  - E2E spec resets state via proxied `/addresses` so no per-project env is needed.

## 2025-09-14 12:10 UTC

- Frontend e2e: Avoid IPv6 localhost issues by setting Playwright project `baseURL` and `webServer.url` to `http://127.0.0.1` for both PG and DB2 projects to prevent ECONNREFUSED(::1) during readiness checks and API resets.

## 2025-09-14 12:15 UTC

- Frontend e2e: Move Playwright `webServer` to a top-level array launching both `ng serve` instances (4200 for PG, 4201 for DB2) so tests reliably wait for servers before running per-project specs.

## 2025-09-14 12:25 UTC

- Frontend e2e cleanup: Remove redundant `frontend/playwright.db2.config.ts`. Update npm scripts `e2e:db2` and `e2e:db2:ui` to use `--project db2-chromium` within the unified matrix config.

## 2025-09-14 12:30 UTC

- Frontend e2e typings: Remove per-project `webServer` and per-project `env` to satisfy Playwright 1.48 type definitions. Use a single top-level `webServer` (`start:matrix`) and per-project `baseURL` only. Tests reset state via the dev-server proxy.

## 2025-09-14 12:45 UTC

- API: Deduplicate repeated string literals in `postfix_blocker/api.py` by introducing constants for route paths, JSON keys, and status/error messages. This reduces refactor risk and silences the linter warning about duplicated strings.

## 2025-09-14 12:55 UTC

- Blocker resilience: Make `postfix_blocker/blocker.py` retry `init_db` with backoff until the database is ready (particularly for DB2, which can take minutes). Prevents rapid supervisor restarts and unblocks e2e DB2 runs.

## 2025-09-14 13:05 UTC

- Tests: Add `tests/conftest.py` to optionally run `docker compose down` and `docker compose up --build -d` before tests. Enabled automatically when backend/e2e tests are collected, or force with `PYTEST_COMPOSE_ALWAYS=1` or `--compose-rebuild`.

## 2025-09-14 13:20 UTC

- Docs: Add production (RHEL 9.5, no Docker) deployment instructions for `postfix_blocker/blocker.py` and `postfix_blocker/api.py` to `INSTALL.md`, including systemd units, SELinux notes, and Postfix integration.

## 2025-09-14 13:30 UTC

- Docker: Rebase `docker/postfix/Dockerfile` to CentOS Stream 9 (RHEL 9 family). Switch to `dnf`, install `postfix`, `rsyslog`, `supervisor`, and `python3`. Keep optional DB2 deps via `ENABLE_DB2` with `pip3`. Aligns local dev env with RHEL 9.5.

## 2025-09-14 13:35 UTC

- Docker: Flip base to Rocky Linux 9 for closer parity with RHEL 9.5. Update README accordingly.

## 2025-09-14 13:38 UTC

- Docker: Enforce PCRE map support in images by asserting `postconf -m` lists `pcre` (built-in on RHEL/Rocky 9). Update README/INSTALL with PCRE requirement and behavior notes.

## 2025-09-14 13:45 UTC

- Blocker: Add runtime guard in `postfix_blocker/blocker.py` to preflight `postconf -m` and log a clear error once on startup when PCRE support is missing.

## 2025-09-14 13:48 UTC

- Blocker: Emit a warning when regex entries exist but Postfix PCRE support is missing, including the count of regex rules that will not be enforced.
## 2025-09-14 13:52 UTC

- Docker: Switch base image reference to `rockylinux/rockylinux:9` (OSS‑sponsored upstream image) instead of the legacy `rockylinux:9` library image. README notes the rationale.

## 2025-09-14 13:58 UTC

- Docker: Skip installing DB2 Python drivers on non‑x86_64 architectures (e.g., arm64) to avoid build failures; log the skip. README clarifies DB2 support is x86_64 for local builds; tests will skip accordingly on other arches.

## 2025-09-14 14:10 UTC

- Frontend: Add bulk input support to UI. New textarea accepts one email/regex per line and an "Add List" action posts entries sequentially (duplicates/blank lines ignored). Unit and e2e tests updated.

## 2025-09-14 14:20 UTC

- Frontend: Simplify UI to a single paste box + Regex toggle and a single "Add" button. Removed the separate single-add input. Updated unit/e2e tests and selectors accordingly.

## 2025-09-14 14:25 UTC

- Frontend tests: Stabilize unit test timing for paste-box add by awaiting a microtask before asserting the first POST request.

## 2025-09-14 14:32 UTC

- Frontend: Add multi-select with per-item checkboxes, a "Select all" master checkbox, and buttons to "Delete Selected" and "Delete All". Deletions are processed sequentially and the list reloads afterward. Unit/e2e tests updated.

## 2025-09-14 14:40 UTC

- Frontend: Modernize UI with Angular Material (toolbar, cards, form field, checkboxes, buttons, list, icons, progress bar). Add Material theme and animations. Update e2e selectors for Material DOM.

## 2025-09-14 14:50 UTC

- Frontend: Improve selection UX — list items highlight when selected, clicking an item toggles selection, and click‑drag across items performs multi‑select/deselect. Added visual style for selected rows.

## 2025-09-14 17:10 UTC

- Frontend: Present block list emails in an Angular Material data table with sorting, pagination, and filtering:
  - Add a quick client-side filter input above the table (current page only).
  - Keep server-side sorting/pagination/filtering for scalability and integrate with `mat-sort` and `mat-paginator`.
  - Show a `matNoDataRow` message when filters yield no results.
- Frontend e2e: Update Playwright spec to target the Material table (rows, checkboxes) instead of the previous list view.

## 2025-09-14 17:40 UTC

- Frontend: Clean up block list table UI
  - Remove duplicate header row and the Search/Sort-by/Direction controls; keep a single Filter box.
  - Enable sorting by clicking table headers (Angular Material `mat-sort` retained).
  - Replace truncated "de" text in Actions with a trash icon (inline SVG; no external icon font required).
  - Add inline editing: double-click a Pattern cell to edit in-place; press Enter or blur to save. Uses new backend update endpoint.
- Backend API: Add `PUT /addresses/<id>` (also accepts `PATCH`) to update `pattern` and/or `is_regex`; returns 404 if not found and 409 on duplicate pattern.

## 2025-09-14 17:55 UTC

- Frontend: Fix inline edit double-submit (Enter + blur) causing duplicate rows by guarding and closing the editor before save.

## 2025-09-14 18:05 UTC

- Frontend: Improve inline editing UX — stop auto-selecting the entire email on edit so partial edits are easy. Input now focuses without selecting all text.

## 2025-09-14 18:30 UTC

- Blocker/Test Mode: Add per-entry "test_mode" support
  - DB: Add `test_mode` boolean column (defaults to true) with an automatic migration for existing tables (PostgreSQL + DB2).
  - Postfix maps: Maintain two sets of access maps — enforced (`blocked_recipients`, `.pcre`) and test-only (`blocked_recipients_test`, `.pcre`).
  - Postfix config: Use `warn_if_reject` with the test maps so they log would-be rejections without blocking.
  - API: Include `test_mode` in list responses; accept `test_mode` in POST and PUT/PATCH to update entries.
- Frontend: Add Mode column with per-row toggle (Test/Enforce), bulk actions for selected and for all, and default new entries to Test mode.

## 2025-09-14 18:45 UTC

- Tests/Packaging: Make `postfix_blocker/` a proper Python package and `tests/` importable
  - Add `postfix_blocker/__init__.py` so `from postfix_blocker import blocker` resolves to this repo’s module.
  - Add `tests/__init__.py` so absolute imports like `from tests.utils_wait ...` work during pytest collection.
  - Update E2E tests to set `test_mode=False` on inserted rows so they remain enforced under the new monitor mode feature.

## 2025-09-14 19:05 UTC

- Static analysis: Add local SonarQube setup and scanner config (later removed; see 19:35 UTC).
## 2025-09-14 19:25 UTC

- Linting (serverless): Add local static analysis without a server
  - Python: Add Ruff, Mypy, and Bandit configs and helper script (`scripts/lint-python.sh`).
  - Frontend: Add ESLint config with `@typescript-eslint` and `eslint-plugin-sonarjs`, npm scripts `lint` and `lint:fix`, and helper script (`scripts/lint-frontend.sh`).
  - Docs: Update TESTING.md with linting instructions. Add `requirements-dev.txt` for Python dev tools.
## 2025-09-14 19:35 UTC

- Cleanup: Remove SonarQube server integration to keep tooling fully serverless
  - Remove `sonarqube` service and volumes from `docker-compose.yml`.
  - Remove `sonar-project.properties` and `scripts/run-sonar-scanner.sh`.
  - Retain serverless linters: Ruff, Mypy, Bandit, and ESLint (sonarjs) remain.

## 2025-09-14 19:50 UTC

- Developer UX: Add pre-commit hooks to run serverless linters automatically
  - `.pre-commit-config.yaml` with Ruff (format+lint), Mypy, Bandit, and ESLint (frontend).
  - `requirements-dev.txt`: add `pre-commit`.
  - `TESTING.md`: instructions to install, enable, and run `pre-commit`.

## 2025-09-14 20:10 UTC

- Lint fixes: Make pre-commit pass cleanly
  - Python: Sort/format imports, modernize type hints to built-in generics and `|` unions, replace asserts with explicit errors, and switch Postfix execs to `subprocess.run` with absolute paths.
  - Bandit: Remove broad `try/except: pass`, add targeted `# nosec` justifications where appropriate, and avoid binding API to all interfaces by default (container sets `API_HOST=0.0.0.0`).
  - Frontend: Add ESLint flat config `frontend/eslint.config.cjs` for ESLint v9.

## 2025-09-15 00:15 UTC

- Frontend dev-server warnings: remove deprecated `--disable-host-check` and silence prebundle warning
  - package.json: drop `--disable-host-check` from `start:devc` and `start:db2`.
  - angular.json: set `serve.options.prebundle=false` to avoid the “Prebundling ... not used because scripts optimization is enabled” message.

## 2025-09-15 01:55 UTC

- Observability: Add structured logging for API and blocker
  - API: per-request logs (start, end with duration, and exceptions). Configurable via `API_LOG_LEVEL` and optional rotating file via `API_LOG_FILE`.
  - Blocker: log map preparation counts, bytes written per file, and each postmap/reload invocation. Configurable via `BLOCKER_LOG_LEVEL` and rotating file `BLOCKER_LOG_FILE` (defaults to `/var/log/postfix-blocker/blocker.log`).
  - Docker: forward `api` and `blocker` stdout/stderr to Docker logs by setting `stdout_logfile=/dev/stdout` and `redirect_stderr=true` in supervisord. Ensure `/var/log/postfix-blocker` exists in image.
