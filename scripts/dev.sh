#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

( cd backend && uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload ) &
BACK_PID=$!

( cd frontend && pnpm dev --port 5173 --host 127.0.0.1 ) &
FRONT_PID=$!

trap "kill $BACK_PID $FRONT_PID 2>/dev/null || true" EXIT
wait
