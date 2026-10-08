#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == "--help" ]]; then
  echo 'Install Atlas dependencies from an extracted Linux release: bash scripts/install-linux.sh'
  exit 0
fi
cd "$(dirname "$0")/.."
if [[ "$(uname -s)" != Linux ]]; then
  echo 'Run this installer on Linux. The Mac development environment is separate.' >&2
  exit 1
fi
PYTHON_BIN="${ATLAS_PYTHON:-python3}"
"$PYTHON_BIN" -c 'import sys; assert sys.version_info >= (3,12), "Python 3.12+ is required"'
if [[ ! -f dist/index.html ]]; then
  echo 'Missing built frontend. Transfer the Linux release archive, or run npm ci && npm run build first.' >&2
  exit 1
fi
if [[ -f .venv/pyvenv.cfg ]] && ! .venv/bin/python -c 'import sys; assert sys.platform == "linux"' 2>/dev/null; then
  echo 'A non-Linux .venv was copied here. Move it aside and rerun; do not migrate a Mac virtualenv.' >&2
  exit 1
fi
"$PYTHON_BIN" -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements.lock
if [[ ! -f deploy/atlas.env ]]; then
  (umask 077; cp deploy/atlas.env.example deploy/atlas.env)
fi
mkdir -p data
echo 'Installed. Start with: ./scripts/start-linux.sh'
echo 'For a persistent service: sudo ./scripts/install-service.sh YOUR_LINUX_USER'
