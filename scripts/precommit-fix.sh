#!/usr/bin/env bash
set -euo pipefail

echo "[precommit-fix] Running Ruff format + fix (postfix_blocker + tests)..."
python -m ruff format postfix_blocker tests || true
python -m ruff check --fix postfix_blocker tests || true

if [ -d "frontend" ]; then
  echo "[precommit-fix] Running ESLint --fix (frontend)..."
  (cd frontend && if [ -d node_modules ]; then npm run lint:fix || true; else echo "[precommit-fix] Skipping ESLint: node_modules not installed"; fi)
fi

echo "[precommit-fix] Restaging files..."
git add -A

echo "[precommit-fix] Running pre-commit hooks..."
pre-commit run --all-files

echo "[precommit-fix] Done."
