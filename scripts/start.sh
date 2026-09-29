#!/usr/bin/env bash
# Starts the three processes the app needs: the document-processing sidecar
# (services/ingest-engine), the Python engine service, and the React frontend
# dev server. See README.md "Running the app" for the environment variables
# this respects. Ctrl+C stops all three.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

export CREDITIQ_DATA_ROOT="${CREDITIQ_DATA_ROOT:-$ROOT_DIR/workflow/data}"
API_PORT="${API_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-4173}"
export INGEST_PORT="${INGEST_PORT:-3102}"
export CREDITIQ_INGEST_URL="${CREDITIQ_INGEST_URL:-http://127.0.0.1:${INGEST_PORT}}"

for need in .venv node_modules services/ingest-engine/node_modules; do
  if [ ! -d "$need" ]; then
    echo "error: $need not found. See README.md, one-time setup." >&2
    exit 1
  fi
done

PIDS=()
cleanup() {
  for pid in "${PIDS[@]:-}"; do
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      wait "$pid" 2>/dev/null || true
    fi
  done
}
trap cleanup EXIT INT TERM

wait_for() {
  local url=$1 name=$2
  for _ in $(seq 1 60); do
    if curl -sS -o /dev/null "$url" 2>/dev/null; then return 0; fi
    sleep 0.5
  done
  echo "error: $name did not become healthy at $url" >&2
  exit 1
}

echo "Starting document-processing sidecar on http://127.0.0.1:${INGEST_PORT}"
(cd services/ingest-engine && exec npm start) &
PIDS+=($!)
wait_for "http://127.0.0.1:${INGEST_PORT}/v1/health" "the sidecar"

echo "Starting engine service on http://localhost:${API_PORT} (CREDITIQ_DATA_ROOT=${CREDITIQ_DATA_ROOT})"
.venv/bin/uvicorn engine.api:app --port "$API_PORT" &
PIDS+=($!)
wait_for "http://localhost:${API_PORT}/api/health" "the engine service"

echo "All services are up."
echo "Starting frontend on http://localhost:${FRONTEND_PORT}"
echo "Sign in with any user from config/roles.yaml and the password in that file's auth.demoPassword."
echo

npm run dev -- --port "$FRONTEND_PORT" --strictPort
