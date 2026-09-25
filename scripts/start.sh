#!/usr/bin/env bash
# Starts both processes the app needs: the Python engine service (sign-in,
# cases) and the React frontend dev server. See README.md "Running the app"
# for the two-terminal version and the environment variables this respects.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

export CREDITIQ_DATA_ROOT="${CREDITIQ_DATA_ROOT:-$ROOT_DIR/workflow/data}"
API_PORT="${API_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-4173}"

if [ ! -d .venv ]; then
  echo "error: .venv not found. Run: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt" >&2
  exit 1
fi

if [ ! -d node_modules ]; then
  echo "error: node_modules not found. Run: npm install" >&2
  exit 1
fi

API_PID=""
cleanup() {
  if [ -n "$API_PID" ] && kill -0 "$API_PID" 2>/dev/null; then
    kill "$API_PID" 2>/dev/null || true
    wait "$API_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

echo "Starting engine service on http://localhost:${API_PORT} (CREDITIQ_DATA_ROOT=${CREDITIQ_DATA_ROOT})"
.venv/bin/uvicorn engine.api:app --port "$API_PORT" &
API_PID=$!

for _ in $(seq 1 30); do
  if curl -sS -o /dev/null "http://localhost:${API_PORT}/api/health" 2>/dev/null; then
    break
  fi
  sleep 0.5
done

if ! curl -sS -o /dev/null "http://localhost:${API_PORT}/api/health" 2>/dev/null; then
  echo "error: engine service did not become healthy on port ${API_PORT}" >&2
  exit 1
fi

echo "Engine service is up."
echo "Starting frontend on http://localhost:${FRONTEND_PORT}"
echo "Sign in with any user from config/roles.yaml and the password in that file's auth.demoPassword."
echo

npm run dev -- --port "$FRONTEND_PORT" --strictPort
