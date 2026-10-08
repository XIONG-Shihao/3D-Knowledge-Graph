#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export ATLAS_ENV_FILE="${ATLAS_ENV_FILE:-$PWD/deploy/atlas.env}"
if [[ ! -f "$ATLAS_ENV_FILE" && -f .env ]]; then export ATLAS_ENV_FILE="$PWD/.env"; fi
exec .venv/bin/python scripts/check-ragflow.py
