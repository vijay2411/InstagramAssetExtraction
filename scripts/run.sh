#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

PORT=${PORT:-8000}
cd backend

# Kill whatever is currently listening on $PORT (usually a previous run.sh).
# lsof -ti prints PIDs only; xargs -r skips if empty so we don't error.
if lsof -ti "tcp:$PORT" > /dev/null 2>&1; then
  echo "==> Port $PORT is in use — killing the previous process"
  lsof -ti "tcp:$PORT" | xargs kill -9 2>/dev/null || true
  # Give the OS a beat to release the socket before we bind it again.
  sleep 0.5
fi

# Rebuild frontend if stale
if [ ! -f app/static/index.html ] || [ "$(find ../frontend/src -newer app/static/index.html -print -quit 2>/dev/null)" ]; then
  ( cd ../frontend && pnpm build )
fi

uv run uvicorn app.main:app --host 127.0.0.1 --port "$PORT" &
SERVER_PID=$!
trap "kill $SERVER_PID 2>/dev/null || true" EXIT

for i in $(seq 1 30); do
  if curl -s "http://127.0.0.1:$PORT/api/health" > /dev/null 2>&1; then
    break
  fi
  sleep 0.2
done

open "http://localhost:$PORT" || true
wait $SERVER_PID
