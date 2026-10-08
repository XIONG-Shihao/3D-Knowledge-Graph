"""Verify native RAGFlow dependencies and API without exposing their credentials."""

import argparse
import base64
import json
import socket
import subprocess
import urllib.request
from pathlib import Path


def check(initialize_elastic=False):
    values = json.loads(Path("/etc/ragflow-native/secrets.json").read_text())
    basic = base64.b64encode(("elastic:" + values["elastic"]).encode()).decode()
    headers = {"Authorization": "Basic " + basic}
    if initialize_elastic:
        request = urllib.request.Request(
            "http://127.0.0.1:9200/_security/user/elastic/_password",
            data=json.dumps({"password": values["elastic"]}).encode(),
            headers={**headers, "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=20):
            pass
    with urllib.request.urlopen(
        urllib.request.Request("http://127.0.0.1:9200/_cluster/health", headers=headers), timeout=10
    ) as response:
        if json.load(response)["status"] == "red":
            raise RuntimeError("Elasticsearch cluster health is red.")
    print("Elasticsearch: OK")
    subprocess.run(
        [
            "mysql",
            "--defaults-extra-file=/etc/ragflow-native/mysql-client.cnf",
            "--batch",
            "--skip-column-names",
            "-e",
            "SELECT 1",
            "rag_flow",
        ],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    print("MySQL: OK")
    with urllib.request.urlopen("http://127.0.0.1:9000/minio/health/ready", timeout=10):
        pass
    print("MinIO: OK")
    with socket.create_connection(("127.0.0.1", 6381), timeout=10) as conn:
        channel = conn.makefile("rb")
        password = values["redis"].encode()
        conn.sendall(
            b"*2\r\n$4\r\nAUTH\r\n$" + str(len(password)).encode() + b"\r\n" + password + b"\r\n"
        )
        if channel.readline() != b"+OK\r\n":
            raise RuntimeError("Redis authentication failed.")
        conn.sendall(b"*1\r\n$4\r\nPING\r\n")
        if channel.readline() != b"+PONG\r\n":
            raise RuntimeError("Redis did not answer PING.")
    print("Redis: OK")
    if not initialize_elastic:
        with urllib.request.urlopen(
            "http://127.0.0.1:9380/v1/system/healthz", timeout=20
        ) as response:
            json.load(response)
        with urllib.request.urlopen("http://127.0.0.1:8080/", timeout=10):
            pass
        print("RAGFlow API and UI: OK. Configure models and test document parsing next.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--initialize-elastic", action="store_true")
    args = parser.parse_args()
    try:
        check(args.initialize_elastic)
    except Exception as exc:
        raise SystemExit(
            f"Native readiness check failed ({type(exc).__name__}). Review service logs; no credentials are printed."
        ) from exc
