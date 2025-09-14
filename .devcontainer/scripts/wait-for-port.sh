#!/usr/bin/env bash
set -euo pipefail

PORT="${1:-4200}"
TIMEOUT="${2:-180}"

echo "[devcontainer] Waiting for http://localhost:${PORT} (timeout: ${TIMEOUT}s)" >&2
for ((i=0; i<TIMEOUT; i++)); do
  if curl -fsS "http://localhost:${PORT}" >/dev/null 2>&1; then
    echo "[devcontainer] Port ${PORT} is ready" >&2
    exit 0
  fi
  sleep 1
done
echo "[devcontainer] Timeout waiting for port ${PORT}" >&2
exit 1

