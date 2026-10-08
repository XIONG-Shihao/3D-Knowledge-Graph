# Atlas — Knowledge workspace

A runnable MVP for the two goals in the referenced conversation: organize documents into searchable knowledge, and explore that knowledge as a graph.

Project documents: [Product specification](docs/PRODUCT.md) · [Architecture](docs/ARCHITECTURE.md) · [3D proposal](docs/3D_PROPOSAL.md) · [Native Linux deployment](deploy/LINUX.md).

## Current status

| Area | Status |
|---|---|
| Local knowledge workspace | Implemented: document ingestion, chunks/topics, keyword search, graph exploration and source inspection |
| Chinese support | Implemented: Simplified Chinese interface, English switch, Chinese keyword matching and Unicode graph labels |
| Graph visualization | **2D only**, using Cytoscape; no 3D renderer or view switch is shipped |
| 3D with flat labels | **Proposed**: nodes/connections in 3D, labels upright and facing the screen, overlap handling and the existing source inspector; see [the proposal](docs/3D_PROPOSAL.md) |
| RAGFlow integration | HTTP adapter implemented; live behavior depends on the connected version, configured models and API compatibility |
| Native Linux without Docker | Atlas package and pinned RAGFlow v0.22.1 installation profile prepared for Ubuntu 24.04 x86_64; full native stack installation and document parsing remain unverified on the destination server |
| Users and permissions | Single-user MVP; login and multi-user access control are not implemented |

The 3D proposal changes presentation rather than knowledge extraction. Screen-facing labels address text orientation; crowded labels still require visibility priorities and collision handling. Basic 3D can reuse the existing graph data and source references without a new graph database.

## Run from GitHub on Linux

This repository contains the full Atlas source: `backend/`, `frontend/`, `tests/`, `run.sh`, Node build files, dependency locks and deployment documentation. Compiled frontend assets in `dist/` are also tracked so Linux can run Atlas without building the interface first. Local data, credentials, virtual environments, `node_modules` and release archives are excluded.

On Ubuntu 24.04 x86_64, with Git and Python 3.12+ available:

```bash
sudo apt-get update
sudo apt-get install -y git python3 python3-venv
git clone git@github.com:XIONG-Shihao/3D-Knowledge-Graph.git
cd 3D-Knowledge-Graph
bash scripts/install-linux.sh
bash scripts/start-linux.sh
```

SSH cloning requires your Linux machine to have a GitHub-authorized SSH key. HTTPS cloning is an alternative: `git clone https://github.com/XIONG-Shihao/3D-Knowledge-Graph.git`.

The Linux scripts use **`deploy/atlas.env`**. Stop the foreground process before installing the systemd service or restarting it after configuration changes. For later source updates, use `git pull --ff-only`, rerun `bash scripts/install-linux.sh` to update Python dependencies, then restart Atlas. Edit frontend code and rebuild with the development commands below when needed.

## Run an existing Linux release ZIP

The ZIP is a deployment package: it contains Python backend source, the compiled frontend in `dist/`, examples, documentation and native deployment scripts. It is **not the full development repository**. It omits `run.sh`, `frontend/`, `tests/`, `package.json`, `package-lock.json`, and the TypeScript/Vite build configuration. The same applies to the `.tar.gz` release.

From the extracted `atlas-linux` directory on Ubuntu 24.04 x86_64:

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-venv
bash scripts/install-linux.sh
bash scripts/start-linux.sh
```

The installer creates a Linux `.venv`, installs hashed runtime dependencies and creates `deploy/atlas.env` if it is absent. The startup script uses that environment file and the compiled frontend. Atlas needs Python 3.12+; Node.js and `uv` are not needed to run this release. The separate native RAGFlow installer manages its own build dependencies.

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) on the Linux host, or use the SSH tunnel in [the Linux guide](deploy/LINUX.md) from your Mac. An empty database is seeded with five fictional sample documents unless `KB_SEED_DEMO=false` is set before first startup. API documentation is available at [/docs](http://127.0.0.1:8000/docs).

For automatic startup, stop the foreground process and run `sudo bash scripts/install-service.sh "$(id -un)"` as the Linux user who owns the installation. The guide covers ZIP extraction, service logs, RAGFlow and data migration.

## What you can do

- Create separate knowledge bases and upload Markdown, TXT, text PDFs, and DOCX files (20 MB each).
- Inspect processing states, source chunks, original files, and grouped topics.
- Search document excerpts. Local mode uses BM25-style keyword ranking; connected RAGFlow workspaces use its retrieval API.
- Pan, zoom, filter, and inspect a 2D Cytoscape graph. Select a node or edge to open its source documents.
- Import/export entity graphs as JSON, including RAGFlow's legacy graph response format.
- Retry failed parsing and remove documents. Content persists across restarts in SQLite and local file storage.

## Try it in two minutes

1. Open **Atlas research** → **Graph explorer**.
2. Select **Project Atlas** in the topic panel, then **leads → Alice Chen** in Connections.
3. Open `atlas-strategy.md` to see the author annotation in its source chunk.
4. Open **Search**, enter `Alice`, and follow a result to its source.
5. Create your own knowledge base and upload a document.

## What the local graph means

Local mode groups headings, explicit `[[references]]`, and common keywords into topics. A **covers** edge means a document contains that topic. It does not claim that two entities have a semantic relationship merely because they appear together.

For an explicit relationship, add this to a Markdown/TXT document:

```text
[[Alice Chen]] --leads--> [[Project Atlas]]
```

The graph shows an arrow labeled **leads**, cites that document, and highlights the chunk containing the annotation. This is author-supplied structure, not automatic AI extraction. The interface labels each graph's origin.

## Linux deployment without Docker

Use the prebuilt Linux release and [the step-by-step Chinese guide](deploy/LINUX.md). It includes a native Atlas installer, systemd service, data-migration backup, and a pinned native RAGFlow profile for Ubuntu 24.04 x86-64. The native stack requires verification on the destination server. No Docker is used.

## Chinese language support

The interface defaults to Simplified Chinese. Use the **English / 中文** button to switch; the choice persists. Document contents, names, and graph labels keep their original language. Local search supports Chinese character bigrams and highlights Chinese query terms. TXT/Markdown accept UTF-8, UTF-16 with a BOM, and GB18030. Upload `examples/中文项目说明.md` to try Chinese search and explicit relationship annotations. Semantic Chinese search in RAGFlow requires a Chinese-capable embedding model.

## Connect RAGFlow

RAGFlow is a separate service. For the complete native Linux deployment requested here, follow [deploy/LINUX.md](deploy/LINUX.md). Its installer prepares the pinned Python service chain and its dependencies. You still need to configure embedding/chat models and create your own RAGFlow API key. Existing or hosted servers can be connected using the same adapter.

For the Linux release, run `scripts/install-linux.sh` first, then edit **`deploy/atlas.env`**. Both `scripts/start-linux.sh` and the installed systemd service explicitly load that file. Editing `.env` will not configure those startup paths.

For a full development checkout started with `run.sh` or the development commands below, copy `.env.example` to `.env` and edit `.env` instead. Set these values in the environment file used by your startup path, then restart Atlas:

```dotenv
RAGFLOW_BASE_URL=http://localhost:9380
RAGFLOW_API_KEY=your-ragflow-api-key
# Optional; use a model configured on your server:
RAGFLOW_EMBEDDING_MODEL=
```

Create a knowledge base with the **RAGFlow** engine. Leave the dataset ID empty to create a new dataset, or enter an existing dataset ID to attach it. Use datasets with the built-in chunking pipeline; custom ingestion pipelines are not supported here.

Uploads are forwarded to RAGFlow and parsing is started asynchronously. Press **Refresh** to fetch document status and chunks. Refresh also imports documents already in an attached dataset. Atlas retains local IDs mapped to RAGFlow dataset/document/chunk IDs. Credentials stay on the Python backend.

The adapter uses the [documented HTTP API](https://ragflow.io/docs/dev/http_api_reference) through Python `httpx`. RAGFlow also has an [official Python SDK](https://ragflow.net/docs/python_api_reference); using HTTP here keeps timeout/error handling consistent across document and graph operations.

### RAGFlow graph compatibility

RAGFlow releases differ. Newer releases organize knowledge graphs as knowledge-compilation artifacts. The current HTTP reference no longer lists the older standalone graph endpoints. This MVP does **not** claim to automate every current artifact operation.

- **Portable path:** generate a Graph artifact in your RAGFlow UI, obtain its graph JSON (if your release exposes an export), and use **Import graph** in Atlas. Otherwise, supply graph JSON from your extraction tool using the schema below.
- **Legacy path:** if your server supports `/knowledge_graph`, `/run_graphrag`, and `/trace_graphrag`, set `RAGFLOW_LEGACY_GRAPH_API=true`. Atlas exposes **Build in RAGFlow** and **Fetch graph & status**. Configure GraphRAG on the RAGFlow dataset first. Missing endpoints return a clear compatibility error.

An imported graph is labeled as imported. Source IDs resolve only against documents/chunks in the current workspace. Unknown IDs remain visible as supplied references; Atlas does not invent citations or treat imported statements as verified facts.

### Graph JSON

Download a template from the graph explorer. A minimal graph:

```json
{
  "nodes": [
    {"id": "alice", "label": "Alice Chen", "type": "person"},
    {"id": "atlas", "label": "Project Atlas", "type": "project"}
  ],
  "edges": [
    {"source": "alice", "target": "atlas", "relation": "leads",
     "description": "Alice leads Project Atlas.",
     "source_documents": ["YOUR_LOCAL_DOCUMENT_ID"]}
  ]
}
```

Use the document ID from the API, a RAGFlow document ID, or a synced RAGFlow chunk ID for source references. RAGFlow-style `entity_name`, `entity_type`, `source_id`, and nested `data.graph` are accepted too. Imports are limited to 5 MB, 2,000 nodes, and 5,000 edges. Importing replaces the displayed graph; **Return to document/topic map** restores the local map.

## Architecture

```text
Browser / TypeScript / Cytoscape
              |
          FastAPI
          /     \
 SQLite + files  RAGFlow HTTP adapter
 local parsing   remote parsing / retrieval / legacy graph
              |
   Normalized nodes + edges + source references
```

`backend/main.py` owns application endpoints; `knowledge.py` owns local parsing, topic grouping, ranking, and graph normalization; `ragflow.py` owns the remote API adapter. In the full source repository, `frontend/main.ts` provides the document library, search, graph explorer, and evidence inspector. The release contains its compiled output in `dist/`, not the TypeScript source.

Data is stored in `data/knowledge.sqlite3` and `data/files/`. To back up, stop the app and copy the entire `data/` directory. Credentials, data and installed dependencies are excluded from Git; the compiled `dist/` frontend is tracked for Linux startup. Use `KB_SEED_DEMO=false` before a first launch to start empty, and `KB_DATA_DIR` for a different storage directory.

## Development and verification

**Full development repository only.** These commands require the omitted frontend sources, Node project files and tests; they cannot be run from the deployment ZIP. To edit/rebuild the interface or run the test suite, use the full source checkout.

Development requires Python 3.12+, [uv](https://docs.astral.sh/uv/), and Node.js 20.19+ or 22.12+. In that checkout, `./run.sh` installs dependencies, builds the frontend and starts Atlas using `.env`. For separate development servers and checks:

```bash
uv sync --frozen
npm ci
# Terminal 1
uv run uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
# Terminal 2 (Vite proxies /api to FastAPI)
npm run dev

npm test
uv run pytest -q
uv run ruff check backend tests
npm run build
```

Tests cover ingestion → chunks → topics → graph → search → deletion; workspace scoping; persistence; malformed graph/file inputs; DOCX tables; scanned PDF failures; Chinese keyword search; and a mocked RAGFlow HTTP contract. A live RAGFlow server is needed to verify deployment-specific model configuration and API compatibility.

`scripts/build-linux-release.sh` is included for reference, but rebuilding releases also requires the full development checkout. To check a deployed runtime, use `/api/health` and the document/RAGFlow acceptance steps in [the Linux guide](deploy/LINUX.md).

## MVP limits

This is a **single-user local app** bound to `127.0.0.1`, without login or multi-user authorization. Separate knowledge bases are organizational boundaries, not user access controls. Do not expose it as a shared service until authentication and organization/document permissions are enforced across all endpoints and retrieval.

Local mode has no OCR, embeddings, or generated chat answers. It returns source excerpts. PDF page numbers are retained locally; imported RAGFlow chunks currently have document/chunk citations only. DOCX tables and paragraphs are supported, while images, footnotes, and layout are not preserved.

Parsing uses in-process background tasks. A stopped local upload is marked failed on restart and can be retried. RAGFlow jobs continue remotely; refresh after restarting. A production system needs durable workers, incremental sync, access control, and tighter resource limits. Remote sync fetches up to 10,000 documents/chunks per paginated call and does not support custom ingestion pipelines.
