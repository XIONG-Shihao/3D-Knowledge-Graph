"""Small, explicit compatibility patches to the pinned native source."""

from pathlib import Path


def patch_admin(root: Path):
    path = root / "admin/server/admin_server.py"
    text = path.read_text()
    for old, new in [
        ('hostname="0.0.0.0"', 'hostname="127.0.0.1"'),
        ("use_debugger=True", "use_debugger=False"),
    ]:
        if new in text:
            continue
        if text.count(old) != 1:
            raise ValueError(
                "Pinned admin source differs from the verified layout; refusing to patch."
            )
        text = text.replace(old, new)
    path.write_text(text)


def use_official_package_index(root: Path):
    # Keep all pinned versions and hashes, but fetch the same artifacts from PyPI.
    for filename in ["pyproject.toml", "uv.lock"]:
        path = root / filename
        text = path.read_text()
        for mirror in ["https://mirrors.aliyun.com/pypi", "https://pypi.tuna.tsinghua.edu.cn"]:
            text = text.replace(mirror + "/simple", "https://pypi.org/simple")
            text = text.replace(mirror + "/packages/", "https://files.pythonhosted.org/packages/")
        path.write_text(text)


if __name__ == "__main__":
    import sys

    patch_admin(Path(sys.argv[1]))
    use_official_package_index(Path(sys.argv[1]))
