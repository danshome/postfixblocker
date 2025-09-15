#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."/frontend
echo "Running ESLint..."
npm run lint

