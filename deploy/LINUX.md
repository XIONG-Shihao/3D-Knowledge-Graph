# Linux 原生部署（不使用 Docker）

本发布包包含 **Atlas 应用**和 **RAGFlow 原生安装配置**。目标环境为 **Ubuntu 24.04 x86-64**。Atlas 只需 Python 3.12+；完整 RAGFlow 建议至少 4 核、16 GB 内存、50 GB 可用磁盘，32 GB 内存和更多磁盘能给文档解析及前端构建留出余量。

这些脚本已经过静态检查与离线配置测试；当前开发电脑是 Mac，**尚未在目标 Linux 服务器上执行完整安装**。安装完成后必须通过下文的服务检查和文档测试，才能确认该服务器可用。

## 1. 把发布包上传到 Linux

### 推荐：从 GitHub 获取完整源码

GitHub 仓库现在包含完整源码、测试、构建文件和编译后的 `dist/`。在 Ubuntu 24.04 x86-64 执行：

```bash
sudo apt-get update
sudo apt-get install -y git python3 python3-venv
git clone git@github.com:XIONG-Shihao/3D-Knowledge-Graph.git
cd 3D-Knowledge-Graph
bash scripts/install-linux.sh
bash scripts/start-linux.sh
```

SSH 克隆需要 Linux 上有 GitHub 授权的 SSH 密钥。也可使用 HTTPS：`git clone https://github.com/XIONG-Shihao/3D-Knowledge-Graph.git`。此启动方式使用 **`deploy/atlas.env`**，无需 Node.js 或 `uv` 来运行 Atlas。`run.sh` 是源码开发启动方式，需要 `uv` 和 Node.js，并使用 `.env`；不要混用两种配置文件。

后续更新：先执行 `git pull --ff-only`，再执行 `bash scripts/install-linux.sh` 更新 Python 依赖，最后重启 Atlas。已有 Linux 部署的 `data/` 和 `deploy/atlas.env` 不在 Git 中，需单独保留；从旧 ZIP 迁移时可使用第 5 节备份/恢复流程。下文的服务、SSH 隧道和 RAGFlow 安装步骤同样适用于源码克隆目录。

### 可选：使用已有 ZIP / tar.gz 发布包

Mac 上已生成 `releases/atlas-linux-0.1.0.tar.gz` 和内容相同的 `releases/atlas-linux-0.1.0.zip`，包含 Python 后端源码、编译后的界面、Python 依赖锁、原生服务脚本、文档和示例。它们是部署包，不是完整开发源码；不包含 `run.sh`、`frontend/`、`tests/` 或 Node 构建文件，也不包含 `.env`、你的文档数据、Mac 的 `.venv` 或 `node_modules`。

部署包使用 `scripts/install-linux.sh` → `scripts/start-linux.sh`，配置文件是 **`deploy/atlas.env`**。README 中的开发命令只适用于完整源码目录。

如果拿到的是 ZIP，上传 ZIP 及其 `.sha256` 文件，在 Linux 上先安装 `unzip`，然后执行：

```bash
sudo apt-get update
sudo apt-get install -y unzip
sha256sum -c atlas-linux-0.1.0.zip.sha256
unzip atlas-linux-0.1.0.zip
```

解压后进入 `atlas-linux`，执行下文相同的 Python 安装和启动命令。无需再解压 tar.gz。ZIP 和 tar.gz 二选一即可；不要覆盖已有 `data/` 或配置来排查启动问题。

以下以 tar.gz 为例。在 Mac 终端执行（把 `user` 和 `SERVER_IP` 替换成实际值）：

```bash
scp releases/atlas-linux-0.1.0.tar.gz releases/atlas-linux-0.1.0.tar.gz.sha256 user@SERVER_IP:~/
ssh user@SERVER_IP
```

在 Linux 终端执行：

```bash
sha256sum -c atlas-linux-0.1.0.tar.gz.sha256
tar -xzf atlas-linux-0.1.0.tar.gz
cd atlas-linux
sudo apt-get update
sudo apt-get install -y python3 python3-venv
./scripts/install-linux.sh
./scripts/start-linux.sh
```

Atlas 启动后监听 `127.0.0.1:8000`。如果希望重启后自动运行，先按 `Ctrl+C` 停止前台进程，然后执行：

```bash
sudo ./scripts/install-service.sh "$(id -un)"
curl -fsS http://127.0.0.1:8000/api/health
```

返回 `{"status":"ok",...}` 表明应用和 SQLite 可以访问。此检查不代表 RAGFlow 已配置或文档解析已经成功。

应用日志：`sudo journalctl -u atlas -f`。重启应用：`sudo systemctl restart atlas`。

## 2. 安装完整的原生 RAGFlow

建议使用全新的专用 Ubuntu 24.04 x86-64 服务器。安装器需要 sudo，会安装系统包、下载代码和模型、创建服务用户、配置 Elasticsearch 所需的内核参数，并启用以下 systemd 服务。没有容器运行时，也没有 Docker 命令。

| 服务 | 用途 | 本机端口 |
|---|---|---|
| `mysql` | RAGFlow 用户、数据集和文档元数据 | 3306 |
| `ragflow-redis` | 缓存与解析任务队列 | 6381 |
| `ragflow-minio` | 保存原始文件 | 9000 / 控制台 9001 |
| `ragflow-elasticsearch` | 全文及向量检索索引 | 9200 |
| `ragflow-api` | RAGFlow API | 9380 |
| `ragflow-worker` | 执行文档解析任务 | 无公开端口 |
| `ragflow-admin` | 管理 API | 9381 |
| `ragflow-sync` | 数据源同步任务 | 无公开端口 |
| `ragflow-web` | RAGFlow 管理界面 | 8080 |

```bash
sudo ./scripts/install-ragflow-native.sh --install
sudo python3 deploy/verify-native.py
```

首次安装需要访问 Ubuntu 软件源、GitHub、PyPI、Hugging Face、Elasticsearch 和 Node.js 下载站；模型和依赖较大，请给下载和构建留出时间。Atlas 使用的 Node.js 编译产物已包含在发布包中；RAGFlow 的独立管理界面需要在 Linux 上编译，安装器使用私有 Node 目录，不替换系统 Node。

### 为什么固定版本

该配置固定 **RAGFlow v0.22.1 Python 服务链**与 **Elasticsearch 8.11.3**，因为此组合的 Python 入口、Redis 队列配置、模型路径与旧版图谱接口已经在上游源码中核对。它是兼容性评估基线，**不是当前最新版本，也不是经本项目认证的生产部署**。新版 Go 服务链使用不同的依赖和入口，不能只改版本号来替换。

版本、源码提交及模型修订记录在 `deploy/native-versions.json`。安装器校验 RAGFlow、MinIO 的源码提交；Elasticsearch、Node 和 Tika 使用上游校验和。保留 Python 依赖锁中的版本和哈希，将其镜像地址改为官方 PyPI。原生管理服务的监听地址改为本机，并关闭其开发调试器。旧版 Office 解析器使用的 OpenSSL 1.1 兼容库在 RAGFlow 私有目录中解包，使用固定 SHA-256 校验，不替换系统 OpenSSL；它同样属于该旧版本评估配置的升级范围。MinIO 的旧二进制下载地址已失效，因此从固定的官方源码编译。

Atlas 和 RAGFlow 的应用入口、搜索索引、文件存储及专用缓存绑定本机回环地址。通过 SSH 隧道使用这个单用户 MVP。若要开放给多人，需要先添加 Atlas 的登录和文档访问控制，并审查、更新完整上游依赖。

### 配置与数据位置

- RAGFlow 源码和 Python 环境：`/opt/ragflow`。
- RAGFlow 连接配置：`/opt/ragflow/conf/service_conf.yaml`。
- 原生服务密码：`/etc/ragflow-native/secrets.json`（root 可读）。密码由安装器随机生成，不使用上游默认密码。
- Redis 数据：`/var/lib/ragflow-redis`；MinIO 文件：`/var/lib/ragflow-minio`；检索索引：`/var/lib/ragflow-elasticsearch`。
- MySQL 的 `rag_flow` 数据库和专用 `ragflow` 用户，仅授予该数据库权限。

安装器不会删除数据。如果发现已有的安装目录或端口冲突，会停止。部分安装失败时，保留 `/etc/ragflow-native/install-started` 和已有配置后可重试；成功安装后再次运行不会自动升级。

## 3. 在 Mac 浏览器打开 Linux 应用

保持 Linux 服务运行。在 Mac 新开一个终端：

```bash
ssh -N -L 8000:127.0.0.1:8000 -L 8080:127.0.0.1:8080 user@SERVER_IP
```

然后在 Mac 浏览器打开：

- Atlas：`http://127.0.0.1:8000`。
- RAGFlow 管理界面：`http://127.0.0.1:8080`。

如果 Mac 上原来的 Atlas 正占用 8000，可把隧道的第一个端口改成 `18000`：`-L 18000:127.0.0.1:8000`，浏览器使用 `http://127.0.0.1:18000`。服务器端和 Atlas 连接 RAGFlow 的配置都不用改。

## 4. 连接 RAGFlow：逐步操作

可以把 **Atlas** 理解成整理和展示知识的界面，把 **RAGFlow** 理解成独立的文档处理及搜索引擎。安装服务只是第一步；还要配置模型和 API 密钥。

1. 打开 RAGFlow 管理界面，注册或登录自己的账号。
2. 打开头像下的 **Model providers / 模型供应商**。添加实际可用的模型服务，填写该模型供应商的密钥或本地服务地址。至少配置一个支持中文的 **embedding / 嵌入模型**；生成图谱还需要 **chat / 聊天模型**。在 **System Model Settings / 系统模型设置**选择默认模型。模型不会仅因为安装 RAGFlow 就自动变得可用。
3. 点击 RAGFlow 头像 → **API**，创建或复制 API 密钥。**这是 RAGFlow 的密钥，不是 OpenAI、通义等模型供应商的密钥。**
4. 在 Linux 终端编辑 Atlas 的配置文件：

```bash
nano deploy/atlas.env
```

填写：

```dotenv
RAGFLOW_BASE_URL=http://127.0.0.1:9380
RAGFLOW_API_KEY=这里填你在RAGFlow创建的API密钥
RAGFLOW_EMBEDDING_MODEL=
RAGFLOW_LEGACY_GRAPH_API=true
```

`RAGFLOW_BASE_URL` 是 RAGFlow 的地址，`RAGFLOW_API_KEY` 是让 Atlas 访问你 RAGFlow 账号的通行证。`9380` 是同一 Linux 服务器上的 RAGFlow API，`8000` 是 Atlas。不要混用这两个地址。`RAGFLOW_EMBEDDING_MODEL` 可先留空，使用 RAGFlow 默认模型；如果创建数据集时提示找不到模型，再填服务器实际配置的 `模型名@供应商`。

5. 保存配置后，在 Linux 终端检查连接并重启：

```bash
./scripts/check-ragflow.sh
sudo systemctl restart atlas
```

6. 在 Atlas 中点击 **创建知识库**，把 **知识引擎**选为 **RAGFlow**。数据集 ID 可留空，Atlas 会创建新数据集。已有本地知识库不会自动转换为 RAGFlow 知识库。
7. 上传 `examples/中文项目说明.md`，点击 **刷新**直到“已就绪”。搜索“知识图谱”，并打开来源文档核对内容。这一步才验证了模型、队列、解析与检索整条链路。
8. 图谱生成：在 RAGFlow 数据集内启用、配置 GraphRAG，再通过 Atlas 的 **在 RAGFlow 中生成**与 **获取图谱与状态**查看进度。图谱功能也可以使用 JSON 导入。

当前发布包不自动部署本地 LLM/嵌入模型服务。你可以在 RAGFlow 中连接现有模型供应商，或之后独立安装本地模型运行时。中文语义检索质量取决于实际选择的模型。

## 5. 迁移 Mac 上已有的文档

代码发布包故意不包含文档数据。如果需要迁移已有 Atlas 文档：

1. 停止 Mac 上的 Atlas，确认没有上传或删除操作。
2. 在 Mac 项目目录执行：

```bash
./scripts/migrate-data.sh ./data /tmp/atlas-data.tar.gz
scp /tmp/atlas-data.tar.gz /tmp/atlas-data.tar.gz.sha256 user@SERVER_IP:~/
```

3. 在 Linux 停止 Atlas，验证校验和，备份当前 `data/`，再将数据解压到应用目录：

```bash
sudo systemctl stop atlas
cd ~/atlas-linux
sha256sum -c ~/atlas-data.tar.gz.sha256
mv data "data-before-migration-$(date +%Y%m%d-%H%M%S)"
tar -xzf ~/atlas-data.tar.gz
sudo systemctl start atlas
```

运行这些命令的用户必须是 Atlas 服务用户，或确保恢复的 `data/` 对服务用户可写。SQLite 文件与原始文档可以跨 Mac/Linux 迁移；Mac 的 `.venv` 和 `node_modules` 不可以直接复制使用。

该迁移只包含 Atlas 本地数据。已有 RAGFlow 的 MySQL 数据库、对象文件、索引及 API 密钥需要单独备份迁移；Atlas 的远程 dataset/document ID 并不能重建远程数据。

## 6. 故障排查

```bash
sudo systemctl status atlas ragflow-api ragflow-worker ragflow-web
sudo journalctl -u ragflow-api -u ragflow-worker --since '10 minutes ago'
sudo python3 deploy/verify-native.py
./scripts/check-ragflow.sh
```

- 界面打不开：先检查 systemd 服务和 SSH 隧道，确认 Mac 浏览器访问的本地端口正确。
- API 401：复制 RAGFlow 账号的 API 密钥，检查是否误填了模型供应商密钥。
- 能连接但文档一直排队：检查 `ragflow-worker` 和 `ragflow-redis`；只启动 API 不会完成解析。
- 模型错误：回到 RAGFlow 模型供应商页，检查模型地址、权限及默认嵌入模型。
- MinIO / ES 失败：运行 `verify-native.py` 并查看相应服务日志；不要删除目录来“修复”。
- MySQL 根账号不能通过 Unix socket 连接：安装器假定新 Ubuntu 默认的 root socket 认证，已有数据库需由管理员手动配置专用账号与连接配置。
- 网络下载失败：修复服务器到官方源的网络连接后重试。源码版本、模型权重和软件源可用性都会影响原生安装。

本安装配置参考并核对了 [RAGFlow v0.22.1 源码](https://github.com/infiniflow/ragflow/tree/v0.22.1)、其 `conf/service_conf.yaml`、`api/ragflow_server.py`、`docker/.env`、依赖文件和模型资源路径。新版 [官方源码启动指南](https://ragflow.io/docs/v1.0.0-rc1/launch_ragflow_from_source)仍使用容器提供依赖服务，本发布包提供的是独立维护的无容器 Python 版本配置，而不是官方认证的全原生安装器。
