#!/usr/bin/env bash
# Run after stopping Atlas; take an application-data snapshot for migration.
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "${1:-}" == --help || $# != 2 ]]; then
  echo 'Usage (Atlas stopped): scripts/migrate-data.sh SOURCE_DATA_DIR OUTPUT_ARCHIVE.tar.gz'
  exit 0
fi
exec .venv/bin/python scripts/migrate-data.py "$1" "$2"
