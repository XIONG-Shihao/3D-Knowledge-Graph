#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "${1:-}" == --help || "${1:-}" != --install ]]; then
  echo 'Native RAGFlow profile: sudo scripts/install-ragflow-native.sh --install'
  echo 'Target: fresh Ubuntu 24.04 x86_64, >= 16 GB RAM, >= 50 GB free disk.'
  echo 'Installs MySQL, an isolated Redis service, Elasticsearch, MinIO from source, and pinned RAGFlow Python services.'
  echo 'Reads deploy/native-versions.json; downloads code, packages, and document models. No containers.'
  exit 0
fi
[[ "$(uname -s)" == Linux && "$(uname -m)" == x86_64 && "$EUID" == 0 ]] || { echo 'Use sudo on Ubuntu 24.04 x86_64.' >&2; exit 1; }
source /etc/os-release
[[ "$ID" == ubuntu && "$VERSION_ID" == 24.04 ]] || { echo 'This profile targets Ubuntu 24.04 only.' >&2; exit 1; }
if [[ -f /etc/ragflow-native/install-complete ]]; then
  echo 'Already installed. Run: sudo python3 deploy/verify-native.py'; exit 0
fi
if [[ ! -f /etc/ragflow-native/install-started ]]; then
  # Fail on an existing stack rather than changing unrelated service settings.
  for directory in /opt/ragflow /opt/ragflow-elasticsearch /opt/ragflow-minio; do
    [[ ! -e "$directory" ]] || { echo "Existing $directory: use a fresh host or review the manual guide." >&2; exit 1; }
  done
  for port in 8080 9380 9381 9200 9000 9001 6381; do
    if ss -H -ltn "sport = :$port" | read -r _; then echo "Port $port is in use." >&2; exit 1; fi
  done
  install -d -m 700 /etc/ragflow-native
  cp deploy/native-versions.json /etc/ragflow-native/install-started
fi
NGINX_PRESENT=0
if [[ "$(dpkg-query -W -f='${Status}' nginx 2>/dev/null || true)" == 'install ok installed' ]]; then NGINX_PRESENT=1; fi
apt-get update
apt-get install -y python3 python3-venv python3-dev build-essential pkg-config git curl ca-certificates \
  mysql-server redis-server nginx golang-go libglib2.0-0t64 libgl1 libglx-mesa0 libicu-dev libgdiplus \
  default-jdk libatk-bridge2.0-0 libgtk-4-1 libnss3 libgbm-dev libjemalloc-dev \
  ghostscript pandoc fonts-noto-cjk unzip libdatrie-dev xz-utils
if [[ "$NGINX_PRESENT" == 0 ]]; then systemctl disable --now nginx.service; fi
systemctl enable --now mysql.service
for account in ragflow ragflow-es ragflow-minio ragflow-redis; do
  id "$account" >/dev/null 2>&1 || useradd --system --create-home --home-dir "/var/lib/$account" --shell /usr/sbin/nologin "$account"
done
install -d -o ragflow -g ragflow /var/log/ragflow /var/lib/ragflow/nginx-body /var/lib/ragflow/nginx-proxy
install -d -o ragflow-es -g ragflow-es /var/log/ragflow-elasticsearch /var/lib/ragflow-elasticsearch
python3 -m venv /opt/ragflow-bootstrap
/opt/ragflow-bootstrap/bin/pip install "uv==0.12.3"
install -m 644 deploy/fetch-ragflow-models.py /opt/ragflow-bootstrap/fetch-ragflow-models.py
install -m 644 deploy/native-versions.json /opt/ragflow-bootstrap/native-versions.json
RAGFLOW_COMMIT="$(python3 -c 'import json; print(json.load(open("deploy/native-versions.json"))["ragflow_commit"])')"
MINIO_COMMIT="$(python3 -c 'import json; print(json.load(open("deploy/native-versions.json"))["minio_commit"])')"
if [[ ! -d /opt/ragflow/.git ]]; then
  git clone --depth 1 --branch v0.22.1 https://github.com/infiniflow/ragflow.git /opt/ragflow
fi
[[ "$(git -C /opt/ragflow rev-parse HEAD)" == "$RAGFLOW_COMMIT" ]] || { echo 'RAGFlow revision mismatch.' >&2; exit 1; }
for entry in api/ragflow_server.py rag/svr/task_executor.py admin/server/admin_server.py rag/svr/sync_data_source.py; do
  [[ -f "/opt/ragflow/$entry" ]] || { echo "Missing upstream entry point: $entry" >&2; exit 1; }
done
chown -R ragflow:ragflow /opt/ragflow
python3 deploy/patch-ragflow.py /opt/ragflow
runuser -u ragflow -- /opt/ragflow-bootstrap/bin/uv sync --project /opt/ragflow --python 3.12 --frozen --no-dev
install -d /opt/ragflow-downloads
# Compatibility libraries for the pinned Office parser are isolated in its
# private library directory; Ubuntu's system OpenSSL is not replaced.
curl --fail --location --retry 3 --proto '=https' \
  https://archive.ubuntu.com/ubuntu/pool/main/o/openssl/libssl1.1_1.1.1f-1ubuntu2_amd64.deb \
  -o /opt/ragflow-downloads/libssl1.1.deb
echo '09ee28588a1fb5613ddc6c26a992d5a76931b3cf22c022930da413a5e580599e  /opt/ragflow-downloads/libssl1.1.deb' | sha256sum -c -
dpkg-deb -x /opt/ragflow-downloads/libssl1.1.deb /opt/ragflow/vendor
runuser -u ragflow -- /opt/ragflow/.venv/bin/python /opt/ragflow-bootstrap/fetch-ragflow-models.py /opt/ragflow /opt/ragflow-bootstrap/native-versions.json

# Build MinIO from its pinned upstream source: retired binary download URLs are not used.
if [[ ! -d /opt/ragflow-minio-source/.git ]]; then
  git clone --depth 1 --branch RELEASE.2025-06-13T11-33-47Z https://github.com/minio/minio.git /opt/ragflow-minio-source
fi
[[ "$(git -C /opt/ragflow-minio-source rev-parse HEAD)" == "$MINIO_COMMIT" ]] || { echo 'MinIO revision mismatch.' >&2; exit 1; }
install -d -o ragflow-minio -g ragflow-minio /opt/ragflow-minio
chown -R ragflow-minio:ragflow-minio /opt/ragflow-minio-source
(cd /opt/ragflow-minio-source; runuser -u ragflow-minio -- env GOTOOLCHAIN=auto go build -o /opt/ragflow-minio/minio .)

install -d /opt/ragflow-downloads
if [[ ! -x /opt/ragflow-elasticsearch/bin/elasticsearch ]]; then
  (cd /opt/ragflow-downloads
   curl --fail --location --retry 3 --proto '=https' -O https://artifacts.elastic.co/downloads/elasticsearch/elasticsearch-8.11.3-linux-x86_64.tar.gz
   curl --fail --location --retry 3 --proto '=https' -O https://artifacts.elastic.co/downloads/elasticsearch/elasticsearch-8.11.3-linux-x86_64.tar.gz.sha512
   sha512sum -c elasticsearch-8.11.3-linux-x86_64.tar.gz.sha512
   mkdir -p /opt/ragflow-elasticsearch
   tar -xzf elasticsearch-8.11.3-linux-x86_64.tar.gz --strip-components=1 -C /opt/ragflow-elasticsearch)
fi
python3 deploy/render-native.py
chown -R ragflow-es:ragflow-es /opt/ragflow-elasticsearch
chown ragflow:ragflow /opt/ragflow/conf/service_conf.yaml
chown root:ragflow-redis /etc/ragflow-native/redis.conf
chmod 755 /etc/ragflow-native
if [[ ! -f /etc/ragflow-native/mysql-initialized ]]; then
  EXISTING_DB="$(mysql --protocol=socket -uroot --batch --skip-column-names -e \"SELECT COUNT(*) FROM information_schema.SCHEMATA WHERE SCHEMA_NAME='rag_flow';\")"
  [[ "$EXISTING_DB" == 0 ]] || { echo 'An existing rag_flow database was found. Refusing to take ownership; configure it manually.' >&2; exit 1; }
fi
mysql --protocol=socket -uroot < /etc/ragflow-native/mysql-init.sql
touch /etc/ragflow-native/mysql-initialized
if [[ ! -f /etc/ragflow-native/elastic-initialized ]]; then
  python3 -c 'import json; print(json.load(open("/etc/ragflow-native/secrets.json"))["elastic"])' | \
    runuser -u ragflow-es -- /opt/ragflow-elasticsearch/bin/elasticsearch-keystore add -x -f bootstrap.password
fi
sysctl -p /etc/sysctl.d/80-ragflow-native.conf
systemctl daemon-reload
systemctl enable --now ragflow-redis.service ragflow-minio.service ragflow-elasticsearch.service
READY=0
for attempt in $(seq 1 60); do
  if python3 deploy/verify-native.py --initialize-elastic; then READY=1; break; fi
  sleep 5
done
[[ "$READY" == 1 ]] || { echo 'Dependency readiness failed. Review journalctl -u ragflow-elasticsearch -u ragflow-minio -u ragflow-redis.' >&2; exit 1; }
touch /etc/ragflow-native/elastic-initialized

# Build the RAGFlow administration UI with a managed Node runtime; no global Node replacement.
NODE_VERSION=22.21.1
if [[ ! -x /opt/ragflow-node/bin/node ]]; then
  (cd /opt/ragflow-downloads
   curl --fail --location --retry 3 --proto '=https' -O "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-x64.tar.xz"
   curl --fail --location --retry 3 --proto '=https' -O "https://nodejs.org/dist/v${NODE_VERSION}/SHASUMS256.txt"
   awk -v file="node-v${NODE_VERSION}-linux-x64.tar.xz" '$2==file' SHASUMS256.txt > node.sha256
   [[ -s node.sha256 ]] && sha256sum -c node.sha256
   mkdir -p /opt/ragflow-node
   tar -xJf "node-v${NODE_VERSION}-linux-x64.tar.xz" --strip-components=1 -C /opt/ragflow-node)
fi
(cd /opt/ragflow/web
 runuser -u ragflow -- env PATH="/opt/ragflow-node/bin:$PATH" npm ci
 runuser -u ragflow -- env PATH="/opt/ragflow-node/bin:$PATH" NODE_OPTIONS=--max-old-space-size=8192 npm run build)
systemctl enable --now ragflow-api.service
API_READY=0
for attempt in $(seq 1 60); do
  if curl --fail --silent http://127.0.0.1:9380/v1/system/healthz >/dev/null; then API_READY=1; break; fi
  sleep 5
done
[[ "$API_READY" == 1 ]] || { echo 'RAGFlow API did not start. Review journalctl -u ragflow-api.' >&2; exit 1; }
systemctl enable --now ragflow-worker.service ragflow-admin.service ragflow-sync.service ragflow-web.service
python3 deploy/verify-native.py
touch /etc/ragflow-native/install-complete
echo 'Native services installed. RAGFlow UI: http://127.0.0.1:8080 (use SSH forwarding).'
echo 'Next: configure Chinese-capable models, create a RAGFlow API key, and set it in Atlas deploy/atlas.env.'
