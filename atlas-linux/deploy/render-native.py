"""Render a private, native RAGFlow installation. --prefix supports offline validation."""

import argparse
import json
import secrets
from pathlib import Path


def render(prefix: Path):
    def path(name):
        return prefix / name.lstrip("/")

    def write(name, content, mode=0o600):
        target = path(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        target.chmod(mode)

    secret_path = path("/etc/ragflow-native/secrets.json")
    if secret_path.exists():
        values = json.loads(secret_path.read_text())
    else:
        values = {
            key: secrets.token_hex(24) for key in ["mysql", "redis", "minio", "elastic", "session"]
        }
        write("/etc/ragflow-native/secrets.json", json.dumps(values, indent=2))
    config = {
        "ragflow": {"host": "127.0.0.1", "http_port": 9380},
        "admin": {"host": "127.0.0.1", "http_port": 9381},
        "mysql": {
            "name": "rag_flow",
            "user": "ragflow",
            "password": values["mysql"],
            "host": "127.0.0.1",
            "port": 3306,
            "max_connections": 100,
            "stale_timeout": 300,
            "max_allowed_packet": 1073741824,
        },
        "minio": {"user": "ragflow", "password": values["minio"], "host": "127.0.0.1:9000"},
        "es": {
            "hosts": "http://127.0.0.1:9200",
            "username": "elastic",
            "password": values["elastic"],
        },
        "redis": {"db": 1, "password": values["redis"], "host": "127.0.0.1:6381"},
        "task_executor": {"message_queue_type": "redis"},
        "user_default_llm": {},
    }
    write("/opt/ragflow/conf/service_conf.yaml", json.dumps(config, indent=2), 0o640)
    write(
        "/etc/ragflow-native/ragflow.env",
        f"""DOC_ENGINE=elasticsearch
STORAGE_IMPL=MINIO
PYTHONPATH=/opt/ragflow
PYTHONUNBUFFERED=1
NLTK_DATA=/opt/ragflow/nltk_data
RAGFLOW_SECRET_KEY={values["session"]}
TIKA_SERVER_JAR=file:///opt/ragflow/tika-server-standard-3.0.0.jar
OMP_NUM_THREADS=2
DEVICE=cpu
LD_LIBRARY_PATH=/opt/ragflow/vendor/usr/lib/x86_64-linux-gnu
""",
    )
    write(
        "/etc/ragflow-native/minio.env",
        f"MINIO_ROOT_USER=ragflow\nMINIO_ROOT_PASSWORD={values['minio']}\n",
    )
    write(
        "/etc/ragflow-native/redis.conf",
        f"""bind 127.0.0.1
port 6381
protected-mode yes
requirepass {values["redis"]}
dir /var/lib/ragflow-redis
appendonly yes
appendfsync everysec
daemonize no
supervised no
logfile ""
""",
        0o640,
    )
    write(
        "/etc/ragflow-native/mysql-client.cnf",
        f"[client]\nuser=ragflow\npassword={values['mysql']}\nhost=127.0.0.1\n",
    )
    write(
        "/etc/ragflow-native/mysql-init.sql",
        f"""CREATE DATABASE IF NOT EXISTS rag_flow CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'ragflow'@'127.0.0.1' IDENTIFIED BY '{values["mysql"]}';
CREATE USER IF NOT EXISTS 'ragflow'@'localhost' IDENTIFIED BY '{values["mysql"]}';
GRANT ALL PRIVILEGES ON rag_flow.* TO 'ragflow'@'127.0.0.1';
GRANT ALL PRIVILEGES ON rag_flow.* TO 'ragflow'@'localhost';
""",
    )
    write(
        "/opt/ragflow-elasticsearch/config/elasticsearch.yml",
        """cluster.name: ragflow-native
node.name: ragflow-node
discovery.type: single-node
network.host: 127.0.0.1
http.port: 9200
path.data: /var/lib/ragflow-elasticsearch
path.logs: /var/log/ragflow-elasticsearch
xpack.security.enabled: true
xpack.security.enrollment.enabled: false
xpack.security.http.ssl.enabled: false
xpack.security.transport.ssl.enabled: false
""",
        0o640,
    )
    write("/opt/ragflow-elasticsearch/config/jvm.options.d/heap.options", "-Xms2g\n-Xmx2g\n", 0o640)
    write("/etc/sysctl.d/80-ragflow-native.conf", "vm.max_map_count=262144\n", 0o644)
    write(
        "/etc/ragflow-native/nginx.conf",
        """worker_processes 1;
pid /var/lib/ragflow/nginx.pid;
error_log /var/log/ragflow/nginx-error.log;
events { worker_connections 1024; }
http {
  include /etc/nginx/mime.types;
  default_type application/octet-stream;
  access_log /var/log/ragflow/nginx-access.log;
  client_body_temp_path /var/lib/ragflow/nginx-body;
  proxy_temp_path /var/lib/ragflow/nginx-proxy;
  server {
    listen 127.0.0.1:8080;
    server_name localhost;
    root /opt/ragflow/web/dist;
    client_max_body_size 128m;
    location ~ ^/api/v1/admin { proxy_pass http://127.0.0.1:9381; }
    location ~ ^/(api|v1) {
      proxy_pass http://127.0.0.1:9380;
      proxy_http_version 1.1;
      proxy_set_header Host $host;
      proxy_set_header X-Real-IP $remote_addr;
      proxy_read_timeout 300s;
      proxy_buffering off;
    }
    location / { try_files $uri $uri/ /index.html; }
  }
}
""",
        0o644,
    )

    def unit(name, user, command, workdir, after="", environment="", extra=""):
        text = f"""[Unit]
Description=Native RAGFlow {name}
After=network.target {after}
{f"Requires={after}" if after else ""}

[Service]
Type=simple
User={user}
WorkingDirectory={workdir}
{environment}
ExecStart={command}
Restart=on-failure
RestartSec=10
UMask=0077
NoNewPrivileges=true
LimitNOFILE=65536
TimeoutStopSec=60
{extra}

[Install]
WantedBy=multi-user.target
"""
        write(f"/etc/systemd/system/ragflow-{name}.service", text, 0o644)

    unit(
        "elasticsearch",
        "ragflow-es",
        "/opt/ragflow-elasticsearch/bin/elasticsearch",
        "/opt/ragflow-elasticsearch",
        extra="Environment=ES_PATH_CONF=/opt/ragflow-elasticsearch/config\nLimitMEMLOCK=infinity",
    )
    unit(
        "redis",
        "ragflow-redis",
        "/usr/bin/redis-server /etc/ragflow-native/redis.conf",
        "/var/lib/ragflow-redis",
    )
    unit(
        "minio",
        "ragflow-minio",
        "/opt/ragflow-minio/minio server --address 127.0.0.1:9000 --console-address 127.0.0.1:9001 /var/lib/ragflow-minio",
        "/var/lib/ragflow-minio",
        environment="EnvironmentFile=/etc/ragflow-native/minio.env",
    )
    dependencies = (
        "mysql.service ragflow-redis.service ragflow-minio.service ragflow-elasticsearch.service"
    )
    env = "EnvironmentFile=/etc/ragflow-native/ragflow.env"
    unit(
        "api",
        "ragflow",
        "/opt/ragflow/.venv/bin/python api/ragflow_server.py",
        "/opt/ragflow",
        dependencies,
        env,
    )
    unit(
        "worker",
        "ragflow",
        "/opt/ragflow/.venv/bin/python rag/svr/task_executor.py native_0",
        "/opt/ragflow",
        "ragflow-api.service",
        env,
    )
    unit(
        "admin",
        "ragflow",
        "/opt/ragflow/.venv/bin/python admin/server/admin_server.py",
        "/opt/ragflow",
        "ragflow-api.service",
        env,
    )
    unit(
        "sync",
        "ragflow",
        "/opt/ragflow/.venv/bin/python rag/svr/sync_data_source.py",
        "/opt/ragflow",
        "ragflow-api.service",
        env,
    )
    unit(
        "web",
        "ragflow",
        "/usr/sbin/nginx -c /etc/ragflow-native/nginx.conf -g 'daemon off;'",
        "/opt/ragflow",
        "ragflow-api.service",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefix", type=Path, default=Path("/"))
    render(parser.parse_args().prefix)
