"""Portable SQLite backup plus original files; no credentials or virtualenv."""

import argparse
import hashlib
import sqlite3
import tarfile
import tempfile
from pathlib import Path


def backup(source: Path, output: Path):
    source = source.resolve()
    if output.resolve().is_relative_to(source):
        raise ValueError("Place the archive outside the source data directory.")
    database = source / "knowledge.sqlite3"
    if not database.is_file():
        raise ValueError("Source does not contain knowledge.sqlite3")
    if output.exists():
        raise ValueError("Choose a new archive path; existing backups are not overwritten.")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as scratch:
        snapshot = Path(scratch) / "knowledge.sqlite3"
        with sqlite3.connect(database) as db, sqlite3.connect(snapshot) as target:
            db.backup(target)
        with tarfile.open(output, "w:gz") as archive:
            archive.add(snapshot, arcname="data/knowledge.sqlite3")
            if (source / "files").is_dir():
                archive.add(source / "files", arcname="data/files")
    output.chmod(0o600)
    (output.parent / (output.name + ".sha256")).write_text(
        hashlib.sha256(output.read_bytes()).hexdigest() + "  " + output.name + "\n"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    backup(args.source, args.output)
    print(
        "Portable data backup created. Keep Atlas stopped while taking this backup for a consistent file snapshot."
    )
