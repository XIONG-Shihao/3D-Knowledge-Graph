import importlib.util
import json
import os
import sqlite3
import tarfile
from pathlib import Path

import pytest

from backend.config import Settings

ROOT = Path(__file__).resolve().parent.parent


def load_file(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_native_configs_are_private_consistent_and_stable(tmp_path):
    renderer = load_file("native_render", "deploy/render-native.py")
    renderer.render(tmp_path)
    credential_file = tmp_path / "etc/ragflow-native/secrets.json"
    first = json.loads(credential_file.read_text())
    renderer.render(tmp_path)
    assert json.loads(credential_file.read_text()) == first
    assert credential_file.stat().st_mode & 0o777 == 0o600
    config = json.loads((tmp_path / "opt/ragflow/conf/service_conf.yaml").read_text())
    assert config["ragflow"]["host"] == "127.0.0.1"
    assert config["mysql"]["password"] == first["mysql"]
    assert config["redis"]["host"] == "127.0.0.1:6381"
    assert config["task_executor"]["message_queue_type"] == "redis"
    redis = (tmp_path / "etc/ragflow-native/redis.conf").read_text()
    assert f"requirepass {first['redis']}" in redis
    units = list((tmp_path / "etc/systemd/system").glob("ragflow-*.service"))
    assert len(units) == 8
    assert all(
        "[Install]" in p.read_text() and "Restart=on-failure" in p.read_text() for p in units
    )
    assert (
        "task_executor.py native_0"
        in (tmp_path / "etc/systemd/system/ragflow-worker.service").read_text()
    )
    assert "127.0.0.1:9000" in (tmp_path / "etc/systemd/system/ragflow-minio.service").read_text()
    assert "listen 127.0.0.1:8080" in (tmp_path / "etc/ragflow-native/nginx.conf").read_text()


def test_admin_patch_is_idempotent_and_requires_known_source(tmp_path):
    module = load_file("native_patch", "deploy/patch-ragflow.py")
    source = tmp_path / "admin/server/admin_server.py"
    source.parent.mkdir(parents=True)
    source.write_text('run_simple(hostname="0.0.0.0", use_debugger=True)')
    module.patch_admin(tmp_path)
    module.patch_admin(tmp_path)
    assert source.read_text() == 'run_simple(hostname="127.0.0.1", use_debugger=False)'
    source.write_text("unexpected_new_source()")
    with pytest.raises(ValueError):
        module.patch_admin(tmp_path)


def test_data_backup_is_portable_and_does_not_overwrite(tmp_path):
    module = load_file("migrate_data", "scripts/migrate-data.py")
    source = tmp_path / "source"
    source.mkdir()
    with sqlite3.connect(source / "knowledge.sqlite3") as db:
        db.execute("CREATE TABLE notes(content TEXT)")
        db.execute("INSERT INTO notes VALUES ('中文知识')")
    (source / "files").mkdir()
    (source / "files/doc").write_text("来源文件")
    archive = tmp_path / "backup.tar.gz"
    module.backup(source, archive)
    with tarfile.open(archive) as tar:
        assert tar.extractfile("data/files/doc").read().decode() == "来源文件"
        restored = tmp_path / "restored.sqlite3"
        restored.write_bytes(tar.extractfile("data/knowledge.sqlite3").read())
    with sqlite3.connect(restored) as db:
        assert db.execute("SELECT content FROM notes").fetchone()[0] == "中文知识"
    with pytest.raises(ValueError):
        module.backup(source, archive)
    with pytest.raises(ValueError):
        module.backup(source, source / "files/recursive.tar.gz")


def test_native_package_patch_preserves_dependency_hashes(tmp_path):
    module = load_file("native_package_patch", "deploy/patch-ragflow.py")
    (tmp_path / "pyproject.toml").write_text('url = "https://pypi.tuna.tsinghua.edu.cn/simple"')
    (tmp_path / "uv.lock").write_text(
        'registry = "https://mirrors.aliyun.com/pypi/simple"\nurl = "https://mirrors.aliyun.com/pypi/packages/file.whl"\nhash = "sha256:abcdef"'
    )
    module.use_official_package_index(tmp_path)
    assert '"https://pypi.org/simple"' in (tmp_path / "pyproject.toml").read_text()
    assert "https://files.pythonhosted.org/packages/file.whl" in (tmp_path / "uv.lock").read_text()
    assert 'hash = "sha256:abcdef"' in (tmp_path / "uv.lock").read_text()


def test_native_profile_has_no_container_commands():
    script = (ROOT / "scripts/install-ragflow-native.sh").read_text()
    assert "docker " not in script.lower()
    assert "podman " not in script.lower()
    assert "sha512sum -c" in script
    assert "--python 3.12 --frozen" in script
    assert "/v1/system/healthz" in script


def test_linux_environment_config_is_separate_from_mac_paths(monkeypatch, tmp_path):
    monkeypatch.setenv("KB_DATA_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("RAGFLOW_BASE_URL", "http://127.0.0.1:9380/")
    monkeypatch.setenv("RAGFLOW_API_KEY", "linux-key")
    settings = Settings.from_env()
    assert settings.data_dir == tmp_path / "state"
    assert settings.ragflow_url == "http://127.0.0.1:9380"
    assert settings.ragflow_configured
    assert os.fspath(ROOT) not in settings.ragflow_url
