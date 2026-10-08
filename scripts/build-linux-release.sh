#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
npm run build
mkdir -p releases
python3 - <<'PY'
import hashlib
import stat
import tarfile
import zipfile
from pathlib import Path

root = Path.cwd()
output = root / "releases/atlas-linux-0.1.0.tar.gz"
included = ["backend", "dist", "examples", "docs", "deploy", "scripts", "requirements.lock", "README.md", "pyproject.toml", "uv.lock", ".env.example"]

def filter_member(member):
    parts = Path(member.name).parts
    if "__pycache__" in parts or member.name.endswith((".pyc", "/atlas.env", "/secrets.json")):
        return None
    member.uid = member.gid = 0
    member.uname = member.gname = ""
    return member

with tarfile.open(output, "w:gz") as archive:
    for item in included:
        archive.add(root / item, arcname="atlas-linux/" + item, filter=filter_member)
zip_output = output.with_name("atlas-linux-0.1.0.zip")
with tarfile.open(output, "r:gz") as archive, zipfile.ZipFile(zip_output, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
    for member in archive:
        if not (member.isdir() or member.isfile()):
            raise ValueError(f"Unsupported ZIP member: {member.name}")
        entry = zipfile.ZipInfo(member.name + ("/" if member.isdir() else ""))
        entry.create_system = 3
        entry.compress_type = zipfile.ZIP_DEFLATED
        file_type = stat.S_IFDIR if member.isdir() else stat.S_IFREG
        entry.external_attr = ((file_type | member.mode) << 16) | (0x10 if member.isdir() else 0)
        zipped.writestr(entry, b"" if member.isdir() else archive.extractfile(member).read())

for release in (output, zip_output):
    checksum = hashlib.sha256(release.read_bytes()).hexdigest()
    (release.parent / (release.name + ".sha256")).write_text(f"{checksum}  {release.name}\n")
    print(release)
print("Includes Linux dependency lock and built frontend. Excludes private configuration, data, and Mac binaries.")
PY
