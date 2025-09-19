## Postfix Blocker - Unified Build/CI Makefile
## Usage examples:
##   make ci            # Lint, build, test (unit+backend+e2e), frontend tests
##   make lint          # Python + frontend lint
##   make test          # Python unit tests + frontend unit tests
##   make e2e           # Backend + E2E tests (brings up docker stack)

SHELL := /bin/bash

# Python virtualenv (created on demand)
VENV ?= venv
VENVPY := $(VENV)/bin/python
VENVPIP := $(VENV)/bin/pip

# Commands
PYTHON ?= python3
PIP ?= pip3
NPM ?= npm
DOCKER_COMPOSE ?= docker compose

# Coverage thresholds (can be overridden via environment)
# Minimum Python coverage percentage (lines):
PY_COV_MIN ?= 80
# Minimum frontend (Karma) coverage percentage (statements/lines/functions).
FE_COV_MIN ?= 80
# Minimum frontend branch coverage percentage (branches only; used by Karma via FE_BRANCH_MIN)
FE_COV_MIN_BRANCH ?= 60

# Convenience command aliases
RUFF := $(VENVPY) -m ruff
MYPY := $(VENVPY) -m mypy
BANDIT := $(VENVPY) -m bandit
PYTEST := $(VENVPY) -m pytest
NPM_RUN = cd $(FRONTEND_DIR) && env -u NO_COLOR $(NPM) run

# Locations
PY_SRC_DIR := postfix_blocker
PY_TEST_DIR := tests
PY_FILES := $(PY_SRC_DIR) $(PY_TEST_DIR)
FRONTEND_DIR := frontend

.PHONY: help ci ci-start ci-end init venv install install-python install-frontend clean-venv clean-frontend clean-logs \
	lint lint-python lint-frontend format format-python format-frontend \
	build build-frontend test test-python-unit test-python-backend test-python-e2e test-python-all test-frontend \
	e2e compose-up compose-down docker-rebuild hooks-update \
	package changelog dist dist-clean check-dist version tag release publish-pypi

# Pretty logging helper
define log_step
	@echo "------------------------------------------------------------------"
	@echo "[make] $(1)"
	@echo "------------------------------------------------------------------"
endef

help:
	@echo "Targets:"
	@echo "  make ci                Lint, build, run unit+backend+e2e (Python+frontend)"
	@echo "  make lint              Ruff + ESLint"
	@echo "  make test              Python unit + frontend unit"
	@echo "  make e2e               Backend + E2E tests (starts compose)"
	@echo "  make compose-up        docker compose up --build -d"
	@echo "  make compose-down      docker compose stop (preserves containers, networks, and volumes)"
	@echo "  make compose-down-hard docker compose down -v --remove-orphans (DESTROYS containers, networks, and volumes)"
	@echo "  make hooks-update      Run 'pre-commit autoupdate' to refresh hook pins"
	@echo "  make format            Run formatters (ruff + ESLint --fix)"
	@echo "  make docker-rebuild    docker compose build --no-cache"

ci: ci-start install lint build compose-up test-python-all test-frontend test-frontend-e2e ci-end

ci-start:
	$(call log_step,CI start)
	@mkdir -p logs
	@$(MAKE) clean-logs
	@touch logs/postfix.maillog logs/postfix_db2.maillog logs/postfix.api.log logs/postfix.blocker.log logs/postfix_db2.api.log logs/postfix_db2.blocker.log

ci-end:
	$(call log_step,CI end)

# Bootstrap tools and dependencies
init: venv install

venv:
	$(call log_step,Create virtualenv ($(VENV)))
	@test -d "$(VENV)" || (echo "[venv] Creating $(VENV)" && $(PYTHON) -m venv $(VENV))

install: install-python install-frontend

install-python: venv
	$(call log_step,Install Python deps)
	@echo "[pip] Upgrading pip/setuptools/wheel..."
	@$(VENVPIP) install -U pip setuptools wheel >/dev/null
	@echo "[pip] Installing requirements (+dev)..."
	@$(VENVPIP) install -r requirements.txt >/dev/null
	@$(VENVPIP) install -r requirements-dev.txt >/dev/null || true
	@echo "[pip] Forcing clean reinstall of pytest to avoid site-package corruption..."
	@$(VENVPIP) install --no-cache-dir --force-reinstall -U pytest pytest-cov >/dev/null || true

install-frontend:
	$(call log_step,Install frontend deps (npm ci))
	@echo "[npm] Installing frontend deps (ci)..."
	@cd $(FRONTEND_DIR) && env -u NO_COLOR $(NPM) ci

clean-venv:
	rm -rf $(VENV)

clean-frontend:
	rm -rf $(FRONTEND_DIR)/node_modules $(FRONTEND_DIR)/dist $(FRONTEND_DIR)/.angular $(FRONTEND_DIR)/test-results

clean-logs:
	rm -rf logs/*.*

# Linting / formatting
lint: lint-python lint-frontend

lint-python: venv
	$(call log_step,Python lint: ruff + mypy + bandit)
	@$(RUFF) format $(PY_FILES)
	@$(RUFF) check --fix $(PY_FILES)
	@$(MYPY) $(PY_SRC_DIR)
	@$(BANDIT) -q -r $(PY_SRC_DIR)

lint-frontend:
	$(call log_step,Frontend lint: ESLint --fix)
	@$(NPM_RUN) lint:fix

format: format-python format-frontend

format-python: venv
	$(call log_step,Python format: ruff format + fix)
	@$(RUFF) format $(PY_FILES)
	@$(RUFF) check --fix $(PY_FILES)

format-frontend:
	$(call log_step,Frontend format: ESLint --fix)
	@cd $(FRONTEND_DIR) && $(NPM) run lint:fix || true

# Building
build: build-frontend

build-frontend:
	$(call log_step,Frontend build)
	@$(NPM_RUN) build

# Testing
test: test-python-unit test-frontend

test-python-all: venv
	$(call log_step,Python tests (unit + backend + e2e with coverage))
	@$(PYTEST) --cov=postfix_blocker --cov-report=xml --cov-fail-under=$(PY_COV_MIN)

test-python-unit: venv
	$(call log_step,Python unit tests)
	@$(PYTEST) -m unit

test-python-backend: venv
	$(call log_step,Python backend tests (docker compose))
	@PYTEST_COMPOSE_ALWAYS=1 $(PYTEST) -m backend

test-python-e2e: venv
	$(call log_step,Python E2E tests (docker compose))
	@PYTEST_COMPOSE_ALWAYS=1 $(PYTEST) -m e2e

test-frontend:
	$(call log_step,Frontend unit tests (Karma))
	@cd $(FRONTEND_DIR) && CI=1 FE_COV_MIN=$(FE_COV_MIN) FE_BRANCH_MIN=$(FE_COV_MIN_BRANCH) env -u NO_COLOR $(NPM) test --silent -- --watch=false

test-frontend-e2e:
	$(call log_step,Frontend E2E tests (Playwright))
	@$(NPM_RUN) e2e

# Meta target to run backend and frontend E2E suites and ensure stack is up
e2e: compose-up test-python-backend test-python-e2e test-frontend-e2e

# Docker stack controls
compose-up:
	$(call log_step,Docker compose up --build -d)
	@$(DOCKER_COMPOSE) up -d --build

compose-down:
		$(call log_step,Docker compose stop)
		@$(DOCKER_COMPOSE) stop || true

compose-down-hard:
		$(call log_step,Docker compose down -v --remove-orphans)
		@$(DOCKER_COMPOSE) down -v --remove-orphans || true

docker-rebuild:
	$(call log_step,Docker compose build --no-cache)
	@$(DOCKER_COMPOSE) build --no-cache

# Update pre-commit hooks to latest versions (pins in .pre-commit-config.yaml)
hooks-update: venv
	$(call log_step,pre-commit autoupdate)
	@echo "[pre-commit] Ensuring pre-commit is installed..."
	@$(VENVPIP) install -q pre-commit >/dev/null || true
	@echo "[pre-commit] Running autoupdate..."
	@$(VENVPY) -m pre_commit autoupdate
	@echo "[pre-commit] Done. Review and commit updated .pre-commit-config.yaml."


# ---------------- Packaging / Release ----------------
package: dist

version: venv
	$(call log_step,Compute version via setuptools_scm)
	@$(VENVPIP) -q install -U setuptools_scm[toml] >/dev/null || true
	@$(VENVPY) -c "import setuptools_scm; print(setuptools_scm.get_version())"

dist-clean:
	$(call log_step,Remove build artifacts)
	@rm -rf dist build *.egg-info

check-dist: venv
	$(call log_step,Validate distribution metadata with twine)
	@$(VENVPIP) -q install -U twine >/dev/null || true
	@$(VENVPY) -m twine check dist/*

# Build sdist + wheel using PEP 517/518 tooling
# Uses setuptools_scm to derive version from Git tags.
dist: venv dist-clean
	$(call log_step,Build Python sdist+wheel)
	@$(VENVPIP) -q install -U build twine setuptools_scm[toml] >/dev/null
	@$(VENVPY) -m build
	@$(VENVPY) -m twine check dist/*
	@rm -rf *.egg-info
	@echo "Artifacts created under ./dist"

# Create/annotate a Git tag for the current version and (optionally) a GitHub release
# Requires: Git repo with tags; optional GitHub CLI 'gh' configured with GITHUB_TOKEN.
release: venv
	$(call log_step,Create Git tag (tag-first), generate changelog, push, and GitHub release)
	@set -euo pipefail; \
	if ! command -v git >/dev/null 2>&1; then echo "[git] Git not available; aborting"; exit 1; fi; \
	# Allow manual override of the version via NEW_VERSION or VERSION env vars
	if [ -n "${NEW_VERSION-}" ]; then VERSION="${NEW_VERSION}"; TAG="v$${VERSION}"; OVERRIDDEN=1; else OVERRIDDEN=0; fi; \
	if [ $$OVERRIDDEN -eq 0 ] && [ -n "${VERSION-}" ]; then VERSION="${VERSION}"; TAG="v$${VERSION}"; OVERRIDDEN=1; fi; \
	if [ $$OVERRIDDEN -eq 1 ]; then \
	  echo "[release] Using overridden version $$VERSION"; \
	  if git rev-parse "$${TAG}" >/dev/null 2>&1; then \
	    echo "[git] Tag $${TAG} already exists"; \
	  else \
	    git tag -a "$${TAG}" -m "postfix-blocker $$VERSION" || true; \
	    echo "[git] Created tag $${TAG}"; \
	  fi; \
	else \
	  SEMVER_TAGS=$$(git tag -l 'v[0-9]*.[0-9]*.[0-9]*'); \
	  if [ -z "$$SEMVER_TAGS" ]; then \
	    VERSION="0.0.0"; \
	    TAG="v$$VERSION"; \
	    echo "[release] No existing SemVer tags; creating initial tag $$TAG"; \
	    git tag -a "$$TAG" -m "postfix-blocker $$VERSION" || true; \
	  else \
	    VERSION=$$($(VENVPY) -c "import setuptools_scm; print(setuptools_scm.get_version())") || { echo "[release] Failed to compute version via setuptools_scm"; exit 1; }; \
	    if echo "$$VERSION" | grep -q 'dev'; then \
	      LATEST_SEMVER_TAG=$$(git tag -l 'v[0-9]*.[0-9]*.[0-9]*' | sort -V | tail -n1); \
	      if [ -z "$$LATEST_SEMVER_TAG" ]; then \
	        echo "[release] No SemVer tag found; please create 'vX.Y.Z' and re-run."; \
	        exit 1; \
	      fi; \
	      TAG="$$LATEST_SEMVER_TAG"; \
    	   VERSION="$${TAG#v}"; \
    	   echo "[release] Using latest SemVer tag $$TAG for release build (HEAD not at tag)"; \
  	   else \
    	   TAG="v$$VERSION"; \
    	   if git rev-parse "$$TAG" >/dev/null 2>&1; then \
    	     echo "[git] Tag $$TAG already exists"; \
    	   else \
    	     git tag -a "$$TAG" -m "postfix-blocker $$VERSION" || true; \
    	     echo "[git] Created tag $$TAG"; \
    	   fi; \
   	   fi; \
 	  fi; \
 	fi; \
 			echo "[release] Version=$$VERSION Tag=$$TAG"; \
 			if [ "${AUTO_CHANGELOG-0}" = "1" ]; then \
 			  echo "------------------------------------------------------------------"; \
 			  echo "[make] Generate CHANGELOG.md (AUTO_CHANGELOG=1)"; \
 			  echo "------------------------------------------------------------------"; \
 			  $(VENVPY) scripts/generate_changelog.py > CHANGELOG.md; \
 			  git add CHANGELOG.md; \
 			  git commit -m "chore(release): update changelog for $$VERSION" || true; \
 			fi; \
 			BRANCH=$$(git rev-parse --abbrev-ref HEAD); \
 			echo "------------------------------------------------------------------"; \
 			echo "[git] Pushing $$BRANCH and tag $$TAG to origin"; \
 			echo "------------------------------------------------------------------"; \
 			git push -u origin "$$BRANCH"; \
 			git push origin "$$TAG"; \
 			echo "------------------------------------------------------------------"; \
 			echo "[make] Build Python sdist+wheel for release $$VERSION"; \
 			echo "------------------------------------------------------------------"; \
 			rm -rf dist build *.egg-info; \
 			$(VENVPIP) -q install -U build twine setuptools_scm[toml] >/dev/null; \
 			SETUPTOOLS_SCM_PRETEND_VERSION=$$VERSION $(VENVPY) -m build; \
 			$(VENVPY) -m twine check dist/*; \
 			rm -rf *.egg-info; \
 			if command -v gh >/dev/null 2>&1; then \
 			  gh release create "$$TAG" dist/* -t "postfix-blocker $$VERSION" -n "See CHANGELOG.md for details." || true; \
 			else \
 			  echo "[gh] GitHub CLI not found; upload dist/* to a GitHub Release named $$TAG"; \
 			fi

# Publish to PyPI (requires TWINE_USERNAME/TWINE_PASSWORD or TWINE_API_KEY set)
publish-pypi: dist
	$(call log_step,Upload to PyPI with twine)
	@$(VENVPY) -m twine upload dist/*


# Generate CHANGELOG.md from Git history (Conventional Commits aware)
changelog: venv
	$(call log_step,Generate CHANGELOG.md from Git history)
	@$(VENVPY) scripts/generate_changelog.py > CHANGELOG.md
	@echo "[changelog] Wrote CHANGELOG.md — review and commit."
