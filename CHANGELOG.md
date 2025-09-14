## 2025-09-13 00:00 UTC

- Add IBM DB2 11.5 Docker service in `docker-compose.yml`.
- Make `app/blocker.py` backend-agnostic (DB2 + PostgreSQL):
  - Declare index via SQLAlchemy; remove backend-specific `CREATE INDEX IF NOT EXISTS`.
  - Export `get_blocked_table()` and publish `blocked_table` after initialization.
- Update `app/api.py` to fetch the table via `get_blocked_table()` at runtime.
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
- Backend: Adjust app/blocker.py to avoid duplicate index creation and DB2 warnings; simplify schema.
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

- API resilience: Make `app/api.py` lazily initialize the database and return 503 `{"error": "database not ready"}` when the backend is unavailable (e.g., DB2 startup). This prevents the API process from crashing so the dev proxy no longer shows ECONNRESET and the UI can stay responsive.

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
