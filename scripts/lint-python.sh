#!/usr/bin/env bash
set -euo pipefail

echo "Running ruff (lint + import sort)..."
python -m ruff check app tests
python -m ruff format --check app tests || true

echo "Running mypy (type check)..."
python -m mypy app

echo "Running bandit (security scan)..."
python -m bandit -q -r app

