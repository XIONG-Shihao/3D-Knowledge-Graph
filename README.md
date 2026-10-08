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

**Run it:**

```bash
./run.sh
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). Requires Python 3.12+, [uv](https://docs.astral.sh/uv/), and Node.js 20.19+ or 22.12+. The first launch installs dependencies and seeds five fictional sample documents. API documentation is available at [/docs](http://127.0.0.1:8000/docs).

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

```bash
cp .env.example .env
```

Set these values in `.env`, then restart Atlas:

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

`backend/main.py` owns application endpoints; `knowledge.py` owns local parsing, topic grouping, ranking, and graph normalization; `ragflow.py` owns the remote API adapter. `frontend/main.ts` provides the document library, search, graph explorer, and evidence inspector.

Data is stored in `data/knowledge.sqlite3` and `data/files/`. To back up, stop the app and copy the entire `data/` directory. `.env`, data, dependencies, and build output are excluded from Git. Use `KB_SEED_DEMO=false` before a first launch to start empty, and `KB_DATA_DIR` for a different storage directory.

## Development and verification

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

## MVP limits

This is a **single-user local app** bound to `127.0.0.1`, without login or multi-user authorization. Separate knowledge bases are organizational boundaries, not user access controls. Do not expose it as a shared service until authentication and organization/document permissions are enforced across all endpoints and retrieval.

Local mode has no OCR, embeddings, or generated chat answers. It returns source excerpts. PDF page numbers are retained locally; imported RAGFlow chunks currently have document/chunk citations only. DOCX tables and paragraphs are supported, while images, footnotes, and layout are not preserved.

Parsing uses in-process background tasks. A stopped local upload is marked failed on restart and can be retried. RAGFlow jobs continue remotely; refresh after restarting. A production system needs durable workers, incremental sync, access control, and tighter resource limits. Remote sync fetches up to 10,000 documents/chunks per paginated call and does not support custom ingestion pipelines.
