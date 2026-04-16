#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> Installing backend deps (uv)"
( cd backend && uv venv --quiet && uv pip install -e ".[dev]" )

echo "==> Installing frontend deps (pnpm)"
( cd frontend && pnpm install --silent )

echo "==> Building frontend bundle"
( cd frontend && pnpm build )

echo "==> Priming Demucs weights (~2GB, one-time)"
( cd backend && uv run python -c "from demucs.pretrained import get_model; get_model('htdemucs_ft')" )

echo "Setup done. Run ./scripts/run.sh to start."
