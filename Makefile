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

# Convenience command aliases
RUFF := $(VENVPY) -m ruff
MYPY := $(VENVPY) -m mypy
BANDIT := $(VENVPY) -m bandit
PYTEST := $(VENVPY) -m pytest -q
NPM_RUN = cd $(FRONTEND_DIR) && $(NPM) run

# Locations
PY_SRC_DIR := postfix_blocker
PY_TEST_DIR := tests
PY_FILES := $(PY_SRC_DIR) $(PY_TEST_DIR)
FRONTEND_DIR := frontend

.PHONY: help ci ci-start ci-end init venv install install-python install-frontend clean-venv clean-frontend clean-logs \
	lint lint-python lint-frontend format format-python format-frontend \
	build build-frontend test test-python-unit test-python-backend test-python-e2e test-python-all test-frontend \
	e2e compose-up compose-down docker-rebuild hooks-update

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
	@echo "  make compose-down      docker compose down -v --remove-orphans"
	@echo "  make hooks-update      Run 'pre-commit autoupdate' to refresh hook pins"
	@echo "  make format            Run formatters (ruff + ESLint --fix)"
	@echo "  make docker-rebuild    docker compose build --no-cache"

ci: ci-start install lint build compose-up test-python-all test-frontend test-frontend-e2e ci-end compose-down

ci-start:
	$(call log_step,CI start)

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

install-frontend:
	$(call log_step,Install frontend deps (npm ci))
	@echo "[npm] Installing frontend deps (ci)..."
	@cd $(FRONTEND_DIR) && $(NPM) ci

clean-venv:
	rm -rf $(VENV)

clean-frontend:
	rm -rf $(FRONTEND_DIR)/node_modules $(FRONTEND_DIR)/dist $(FRONTEND_DIR)/.angular $(FRONTEND_DIR)/test-results

clean-logs:
	rm -f logs/*.log

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
	$(call log_step,Python tests (unit + backend + e2e in one run))
	@$(PYTEST) || true

test-python-unit: venv
	$(call log_step,Python unit tests)
	@$(PYTEST) -m unit || true

test-python-backend: venv
	$(call log_step,Python backend tests (docker compose))
	@PYTEST_COMPOSE_ALWAYS=1 $(PYTEST) -m backend || true

test-python-e2e: venv
	$(call log_step,Python E2E tests (docker compose))
	@PYTEST_COMPOSE_ALWAYS=1 $(PYTEST) -m e2e || true

test-frontend:
	$(call log_step,Frontend unit tests (Karma))
	@cd $(FRONTEND_DIR) && CI=1 $(NPM) test --silent -- --watch=false || true

test-frontend-e2e:
	$(call log_step,Frontend E2E tests (Playwright))
	@$(NPM_RUN) e2e || true

# Meta target to run backend and frontend E2E suites and ensure stack is up
e2e: compose-up test-python-backend test-python-e2e test-frontend-e2e

# Docker stack controls
compose-up:
	$(call log_step,Docker compose up --build -d)
	@$(DOCKER_COMPOSE) up -d --build

compose-down:
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
