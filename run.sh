#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
uv sync --frozen --cache-dir "${TMPDIR:-/tmp}/atlas-uv-cache"
if [ ! -d node_modules ]; then
  npm ci --cache "${TMPDIR:-/tmp}/atlas-npm-cache"
fi
npm run build
exec .venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port "${PORT:-8000}"
