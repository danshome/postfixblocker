# Changelog

All notable changes to this project are documented here.
This file is auto-generated from Git history. Do not edit by hand.

## v0.0.0 - 2025-09-16
### Refactoring
- Rename `app` package to `postfix_blocker` for improved clarity and modularity
- Integrate Angular Material components and animations; add server-side pagination, sorting, and filtering; implement inline editing for block list patterns. Update tests and API for new functionality.

### Documentation
- add or update project documentation (README, CONTRIBUTING, LICENSE, etc.)

### Other
- **Remove outdated refactor status documentation**
- Complete refactor milestone: remove blocker.py re-exports, tighten typing in app_factory, and finalize integration tests.
- **Refactor: Modularize Postfix Blocker - Core Services and Helpers**
- - Add `mailtester.sh` script for SMTP testing with various options. - Introduce Playwright E2E test for mode enforcement toggle and delivery behavior. - Update `postfix_blocker/blocker.py` to always fetch entries and apply changes based on marker or content hash.
- Add comprehensive E2E tests and logging improvements
- - Add persistent volume for DB2 data in `docker-compose.yml` - Introduce `_cleanup_api_state` pytest fixture to handle DB2/Addresses cleanup - Update Makefile to add `compose-down-hard` target for volume destruction
- Add `stack_running` helper to optimize compose rebuild logic and integrate `test-python-all` target into Makefile
- Add `log_step` helper for clearer Makefile output and improve task readability
- - Handle DB2 fetchall() returning None for empty results in `postfix_blocker/api.py`. - Increase test timeout to 10 minutes for DB2 initialization in Playwright configuration and tests. - Update Playwright tests to improve stability of row selection and assertion logic. - Remove outdated test result artifacts and mark tests as passed.
- - Add signal-based IPC to synchronize API and blocker refresh efficiently. - Enhance logging to handle handler-level setting failures gracefully. - Optimize E2E tests and unify CI workflow with `make ci`. - Update package dependencies, build config, and improve code formatting. - Improve Postfix blocker database schema handling and refresh flow.
- - Add signal-based IPC to synchronize API and blocker refresh efficiently. - Enhance logging to handle handler-level setting failures gracefully. - Optimize E2E tests and unify CI workflow with `make ci`. - Update package dependencies, build config, and improve code formatting. - Improve Postfix blocker database schema handling and refresh flow.
- Enhance logging configuration for API and blocker, including support for env-provided levels (int/names) and clearer initialization logs. Update supervisord to explicitly pass log-related environment variables.
- - Add debug logging to paginated list API responses - Default blocker log level to DEBUG for enhanced diagnostics - Update docker-compose environment variables to set DEBUG log levels
- Update logging paths to use `/var/log/postfix-blocker`, improve error handling in blocker.py, and update related documentation and configuration files.
- Add repository guidelines to AGENTS.md for structure, testing, and development practices
- Add pre-commit fix script and configure logging for Docker services
- - Add structured logging for API and blocker with optional file-based logs; integrate Docker log forwarding. - Update ESLint pre-commit hook to run lint:fix before fallback to lint. - Refactor and document logging improvements in `blocker` and `api`. - Ensure `/var/log/app` directory exists in Docker build. - Update contribution guidelines for running pre-commit hooks.
- Add pre-commit hooks for serverless lint tooling and ESLint flat config
- Update dependencies in `package-lock.json`:
- Add bulk input functionality to frontend UI
- Add production deployment documentation for RHEL 9.5 and update Docker configurations to align with Rocky Linux 9. Ensure PCRE map support validation and enhance compatibility for non-x86_64 architectures.
- **Tests: Add pytest setup for managing docker-compose lifecycle** Introduce `tests/conftest.py` to enable optional docker-compose lifecycle management during tests. Automatically triggered for backend/e2e tests or can be forced using `PYTEST_COMPOSE_ALWAYS=1` or `--compose-rebuild`. Update `requirements.txt` to include pytest.
- - **Frontend resilience & e2e improvements**:   - Enhance API error handling for database initialization delays (`app/api.py`).   - Update Angular `frontend/angular.json` to fix dev-server configuration.   - Simplify Playwright configuration to a DB2-only project.   - Consolidate to a single `proxy.json` for API proxy and update e2e commands in `package.json`.   - Ensure stable test environments by improving Playwright test setup and avoiding test flakiness.   - Remove redundant reporters in `karma.conf.js` and guard against unnecessary test reloads.
- Migrate Angular app to standalone bootstrap with updated AppComponent and dependencies.
- Replace Jest with Karma for Angular test setup, update dependencies to align with Angular 20.
- Update devcontainer setup: replace `npm ci` with `npm install` in postCreateCommand and update dependencies in `package-lock.json`.
- Add Jest and Playwright configurations to frontend
- Add e2e tests, unit tests, and development container configuration for frontend
- Add e2e tests, unit tests, and development container configuration for frontend
- Add GitHub Actions CI workflow with unit, backend, and end-to-end test jobs; update dependencies and tests for DB2 support.
- - Rename `tests/e2e_demo.py` to `tests/e2e_test.py` and update references. - Add `tests/test_db_backends.py` for optional backend smoke tests. - Update documentation: AGENTS.md and README.md with new test instructions and references.
- Refactor E2E demo script with extended functionality, environment configuration, and mass mail testing. Update Docker setup for improved compatibility and logging.
- Improve e2e demo import and docs
- Fix and document end-to-end demo
- Document project info and broken demo
- Use non-default ports and support Mac
- Fix Docker build context for postfix
- Add postfix blocker service with Docker and UI
- Initial commit
