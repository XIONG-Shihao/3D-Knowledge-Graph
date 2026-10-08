#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == "--help" ]]; then
  echo 'Usage: sudo scripts/install-service.sh NON_ROOT_LINUX_USER'
  exit 0
fi
cd "$(dirname "$0")/.."
if [[ "$(uname -s)" != Linux || "$EUID" != 0 ]]; then
  echo 'Run this on Linux using sudo.' >&2; exit 1
fi
ATLAS_SERVICE_USER="${1:-${SUDO_USER:-}}"
if [[ -z "$ATLAS_SERVICE_USER" || "$ATLAS_SERVICE_USER" == root ]]; then
  echo 'Specify the non-root Linux user that owns this Atlas directory.' >&2; exit 1
fi
id "$ATLAS_SERVICE_USER" >/dev/null
if [[ "$PWD" == *[[:space:]]* || ! -x .venv/bin/python || ! -f deploy/atlas.env ]]; then
  echo 'Use a path without spaces and run install-linux.sh before installing the service.' >&2; exit 1
fi
if ! runuser -u "$ATLAS_SERVICE_USER" -- test -r "$PWD/deploy/atlas.env"; then
  echo 'The service user must be able to read deploy/atlas.env.' >&2; exit 1
fi
if ! runuser -u "$ATLAS_SERVICE_USER" -- test -w "$PWD/data"; then
  echo 'The service user must own the data directory.' >&2; exit 1
fi
python3 - "$PWD" "$ATLAS_SERVICE_USER" <<'PY'
import pathlib, re, sys
root, user = sys.argv[1:]
if not re.fullmatch(r"[A-Za-z0-9_./-]+", root) or not re.fullmatch(r"[a-z_][a-z0-9_-]*", user):
    raise SystemExit("Use a conventional absolute path and Linux username.")
template = pathlib.Path("deploy/atlas.service.template").read_text()
pathlib.Path("/etc/systemd/system/atlas.service").write_text(template.replace("@ROOT@", root).replace("@USER@", user))
PY
systemctl daemon-reload
systemctl enable --now atlas.service
echo 'Atlas installed at http://127.0.0.1:8000. Access remotely through the SSH tunnel in deploy/LINUX.md.'
