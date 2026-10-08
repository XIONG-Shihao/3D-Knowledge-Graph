#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -x .venv/bin/python || ! -f dist/index.html ]]; then
  echo 'Run scripts/install-linux.sh from the Linux release directory first.' >&2
  exit 1
fi
export ATLAS_ENV_FILE="$PWD/deploy/atlas.env"
exec .venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port "${ATLAS_PORT:-8000}" --workers 1
