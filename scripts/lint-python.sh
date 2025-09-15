#!/usr/bin/env bash
set -euo pipefail

echo "Running ruff (format + fix)..."
python -m ruff format postfix_blocker tests || true
python -m ruff check --fix postfix_blocker tests

echo "Running mypy (type check)..."
python -m mypy postfix_blocker

echo "Running bandit (security scan)..."
python -m bandit -q -r postfix_blocker
