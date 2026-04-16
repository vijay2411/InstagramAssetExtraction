#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../backend"
echo "==> Updating yt-dlp to latest"
uv pip install -U yt-dlp
echo "Done."
