#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."/frontend
echo "Running ESLint --fix..."
npm run lint:fix || npm run lint
