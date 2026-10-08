import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import ROOT, Settings
from .knowledge import (
    SUPPORTED,
    extract_topics,
    local_graph,
    normalize_graph,
    parse_file,
    plain_text,
    search_chunks,
)
from .ragflow import RAGFlowClient, RAGFlowError
from .store import Store

logger = logging.getLogger(__name__)


class NewKnowledgeBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=1000)
    backend: Literal["local", "ragflow"] = "local"
    dataset_id: str | None = Field(default=None, max_length=100)


class Query(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


def create_app(settings=None, ragflow=None):
    settings = settings or Settings.from_env()
    store = Store(settings.data_dir)
    rag = ragflow or RAGFlowClient(settings)

    def get_kb(kb_id):
        kb = store.one("SELECT * FROM knowledge_bases WHERE id=?", (kb_id,))
        if not kb:
            raise HTTPException(404, "Knowledge base not found.")
        return kb

    def get_doc(kb_id, doc_id):
        get_kb(kb_id)
        doc = store.one("SELECT * FROM documents WHERE id=? AND kb_id=?", (doc_id, kb_id))
        if not doc:
            raise HTTPException(404, "Document not found in this knowledge base.")
        return doc

    def all_chunks(kb_id):
        return store.all(
            "SELECT c.*,d.name AS document_name,d.kb_id FROM chunks c "
            "JOIN documents d ON c.doc_id=d.id WHERE d.kb_id=? ORDER BY d.created_at,c.ordinal",
            (kb_id,),
        )

    def documents(kb_id):
        rows = store.all(
            "SELECT d.*, (SELECT COUNT(*) FROM chunks c WHERE c.doc_id=d.id) AS chunk_count "
            "FROM documents d WHERE kb_id=? ORDER BY created_at DESC",
            (kb_id,),
        )
        for row in rows:
            row["topics"] = json.loads(row["topics"])
        return rows

    def process_local(doc):
        try:
            chunks, topics = parse_file(doc["name"], (store.files / doc["id"]).read_bytes())
            store.save_chunks(doc["id"], chunks, topics)
        except Exception as exc:
            store.execute(
                "UPDATE documents SET status='failed',error=? WHERE id=?",
                (str(exc)[:500], doc["id"]),
            )

    def dispatch_remote(kb, doc):
        try:
            if not doc.get("remote_id"):
                remote_id = rag.upload(
                    kb["dataset_id"], doc["name"], (store.files / doc["id"]).read_bytes()
                )
                store.execute("UPDATE documents SET remote_id=? WHERE id=?", (remote_id, doc["id"]))
            else:
                remote_id = doc["remote_id"]
            rag.parse(kb["dataset_id"], remote_id)
            store.execute(
                "UPDATE documents SET status='processing',error='' WHERE id=?", (doc["id"],)
            )
        except Exception as exc:
            store.execute(
                "UPDATE documents SET status='failed',error=? WHERE id=?",
                (str(exc)[:500], doc["id"]),
            )

    @asynccontextmanager
    async def lifespan(app):
        # A terminated upload must not remain silently queued after a restart.
        store.execute(
            "UPDATE documents SET status='failed',error='Upload was interrupted. Retry processing.' "
            "WHERE status='queued'"
        )
        if settings.seed_demo and not store.one("SELECT id FROM knowledge_bases LIMIT 1"):
            kb = store.add_kb(
                "Atlas research",
                "A fictional team workspace. Explore the connections, then add your own documents.",
            )
            for path in sorted((ROOT / "examples").glob("*.md")):
                doc = store.add_document(kb["id"], path.name, path.read_bytes())
                process_local(doc)
        yield

    app = FastAPI(title="Atlas Knowledge API", version="0.1.0", lifespan=lifespan)
    app.state.store = store
    app.state.settings = settings

    @app.get("/api/health")
    def health():
        store.one("SELECT 1 AS ok")
        return {
            "status": "ok",
            "storage": "sqlite",
            "ragflow_configured": settings.ragflow_configured,
        }

    @app.exception_handler(RAGFlowError)
    async def ragflow_error(request, exc):
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=502, content={"detail": str(exc)})

    @app.get("/api/config")
    def config():
        return {
            "ragflow_configured": settings.ragflow_configured,
            "legacy_graph_api": settings.legacy_graph_api,
            "max_upload_mb": settings.max_upload_bytes // (1024 * 1024),
            "supported_formats": sorted(SUPPORTED),
            "single_user": True,
        }

    @app.get("/api/knowledge-bases")
    def list_kbs():
        return store.all(
            "SELECT k.*, (SELECT COUNT(*) FROM documents d WHERE d.kb_id=k.id) AS document_count, "
            "(SELECT COUNT(*) FROM chunks c JOIN documents d ON c.doc_id=d.id WHERE d.kb_id=k.id) "
            "AS chunk_count FROM knowledge_bases k ORDER BY k.created_at",
        )

    @app.post("/api/knowledge-bases", status_code=201)
    def create_kb(body: NewKnowledgeBase):
        name = body.name.strip()
        if not name:
            raise HTTPException(422, "A name is required.")
        dataset_id = None
        if body.backend == "ragflow":
            if not settings.ragflow_configured:
                raise HTTPException(
                    422, "Set RAGFLOW_BASE_URL and RAGFLOW_API_KEY in .env, then restart."
                )
            if body.dataset_id:
                if store.one(
                    "SELECT id FROM knowledge_bases WHERE dataset_id=?", (body.dataset_id,)
                ):
                    raise HTTPException(409, "This dataset is already connected to a workspace.")
                dataset = rag.dataset(body.dataset_id)
                if dataset.get("pipeline_id"):
                    raise HTTPException(
                        422,
                        "Use a dataset with built-in chunking. Ingestion pipelines are not supported in this MVP.",
                    )
                dataset_id = body.dataset_id
            else:
                dataset_id = rag.create_dataset(name, body.description)
        return store.add_kb(name, body.description, body.backend, dataset_id)

    @app.get("/api/knowledge-bases/{kb_id}/documents")
    def list_documents(kb_id: str):
        get_kb(kb_id)
        return documents(kb_id)

    @app.post("/api/knowledge-bases/{kb_id}/documents", status_code=202)
    async def upload_document(
        kb_id: str, tasks: BackgroundTasks, file: Annotated[UploadFile, File()]
    ):
        kb = get_kb(kb_id)
        name = Path((file.filename or "untitled").replace("\\", "/")).name[:200]
        if Path(name).suffix.lower() not in SUPPORTED:
            raise HTTPException(415, "Upload Markdown, TXT, PDF, or DOCX.")
        blob = await file.read(settings.max_upload_bytes + 1)
        await file.close()
        if len(blob) > settings.max_upload_bytes:
            raise HTTPException(413, "File exceeds the 20 MB upload limit.")
        if not blob:
            raise HTTPException(422, "The file is empty.")
        doc = store.add_document(kb_id, name, blob)
        if kb["backend"] == "local":
            tasks.add_task(process_local, doc)
        else:
            tasks.add_task(dispatch_remote, kb, doc)
        return doc

    @app.get("/api/knowledge-bases/{kb_id}/documents/{doc_id}")
    def document_detail(kb_id: str, doc_id: str):
        doc = get_doc(kb_id, doc_id)
        doc["topics"] = json.loads(doc["topics"])
        doc["chunks"] = store.all("SELECT * FROM chunks WHERE doc_id=? ORDER BY ordinal", (doc_id,))
        return doc

    @app.get("/api/knowledge-bases/{kb_id}/documents/{doc_id}/download")
    def download_document(kb_id: str, doc_id: str):
        doc = get_doc(kb_id, doc_id)
        path = store.files / doc_id
        if not path.exists():
            raise HTTPException(404, "Original file is only available on the RAGFlow server.")
        return FileResponse(path, filename=doc["name"], media_type="application/octet-stream")

    @app.post("/api/knowledge-bases/{kb_id}/documents/{doc_id}/retry", status_code=202)
    def retry(kb_id: str, doc_id: str, tasks: BackgroundTasks):
        doc = get_doc(kb_id, doc_id)
        kb = get_kb(kb_id)
        if doc["status"] in {"queued", "processing"}:
            raise HTTPException(409, "Processing is already in progress. Refresh status first.")
        if not (store.files / doc_id).exists():
            if kb["backend"] == "ragflow" and doc["remote_id"]:
                rag.parse(kb["dataset_id"], doc["remote_id"])
                store.execute(
                    "UPDATE documents SET status='processing',error='' WHERE id=?", (doc_id,)
                )
                return {"status": "processing"}
            raise HTTPException(404, "Original file is unavailable. Upload it again.")
        store.execute(
            "UPDATE documents SET status='queued',progress=0,error='' WHERE id=?", (doc_id,)
        )
        tasks.add_task(process_local, doc) if kb["backend"] == "local" else tasks.add_task(
            dispatch_remote, kb, doc
        )
        return {"status": "queued"}

    @app.delete("/api/knowledge-bases/{kb_id}/documents/{doc_id}", status_code=204)
    def delete_document(kb_id: str, doc_id: str):
        doc = get_doc(kb_id, doc_id)
        kb = get_kb(kb_id)
        if doc["status"] in {"queued", "processing"}:
            raise HTTPException(409, "Wait for processing to finish before removing this document.")
        if kb["backend"] == "ragflow" and doc["remote_id"]:
            rag.delete_document(kb["dataset_id"], doc["remote_id"])
        store.execute("DELETE FROM documents WHERE id=?", (doc_id,))
        (store.files / doc_id).unlink(missing_ok=True)
        # Cached extracted relationships may depend on this document. Invalidate them.
        store.execute("DELETE FROM graphs WHERE kb_id=?", (kb_id,))
        store.execute(
            "UPDATE knowledge_bases SET graph_status='',graph_error='' WHERE id=?", (kb_id,)
        )

    @app.post("/api/knowledge-bases/{kb_id}/sync")
    def sync(kb_id: str):
        kb = get_kb(kb_id)
        if kb["backend"] == "local":
            return {"documents": documents(kb_id), "message": "Local workspace is up to date."}
        remote_docs = rag.documents(kb["dataset_id"])
        for remote in remote_docs:
            remote_id = remote["id"]
            doc = store.one(
                "SELECT * FROM documents WHERE kb_id=? AND remote_id=?", (kb_id, remote_id)
            )
            if not doc:
                doc = store.add_document(
                    kb_id, remote.get("name", "Remote document"), b"", remote_id
                )
                (store.files / doc["id"]).unlink(missing_ok=True)
                store.execute(
                    "UPDATE documents SET size=? WHERE id=?",
                    (int(remote.get("size", 0) or 0), doc["id"]),
                )
            progress = float(remote.get("progress", 0) or 0)
            run = str(remote.get("run", ""))
            if progress < 0 or run in {"FAIL", "5"}:
                status = "failed"
            elif run in {"CANCEL", "4"}:
                status = "failed"
            elif run in {"DONE", "3"} or progress >= 1:
                status = "ready"
            elif run in {"UNSTART", "0"}:
                status = "unstarted"
            else:
                status = "processing"
            try:
                if status == "ready":
                    raw = rag.chunks(kb["dataset_id"], remote_id)
                    parsed = [
                        {
                            "content": plain_text(
                                c.get("content", c.get("content_with_weight", ""))
                            ),
                            "remote_id": c.get("id"),
                            "keywords": c.get("important_keywords", []),
                        }
                        for c in raw
                        if c.get("available", True)
                    ]
                    topics = list(dict.fromkeys(str(k) for c in parsed for k in c["keywords"]))[:8]
                    if not topics:
                        topics = extract_topics("\n".join(c["content"] for c in parsed))
                    store.save_chunks(doc["id"], parsed, topics)
                else:
                    # Never keep old searchable chunks after a remote parse fails/restarts.
                    store.execute("DELETE FROM chunks WHERE doc_id=?", (doc["id"],))
                    store.execute("DELETE FROM graphs WHERE kb_id=?", (kb_id,))
                    store.execute(
                        "UPDATE documents SET status=?,progress=?,error=? WHERE id=?",
                        (
                            status,
                            max(0, min(1, progress)),
                            str(remote.get("progress_msg", ""))[:500] if status == "failed" else "",
                            doc["id"],
                        ),
                    )
            except RAGFlowError as exc:
                store.execute("DELETE FROM chunks WHERE doc_id=?", (doc["id"],))
                store.execute("DELETE FROM graphs WHERE kb_id=?", (kb_id,))
                store.execute(
                    "UPDATE documents SET status='failed',error=? WHERE id=?", (str(exc), doc["id"])
                )
        remote_ids = {d["id"] for d in remote_docs}
        stale = store.all(
            "SELECT id,remote_id FROM documents WHERE kb_id=? AND remote_id IS NOT NULL", (kb_id,)
        )
        removed = False
        for doc in stale:
            if doc["remote_id"] not in remote_ids:
                store.execute("DELETE FROM documents WHERE id=?", (doc["id"],))
                (store.files / doc["id"]).unlink(missing_ok=True)
                removed = True
        if removed:
            store.execute("DELETE FROM graphs WHERE kb_id=?", (kb_id,))
        return {"documents": documents(kb_id), "message": "RAGFlow status and chunks refreshed."}

    @app.get("/api/knowledge-bases/{kb_id}/topics")
    def topics(kb_id: str):
        get_kb(kb_id)
        grouped = {}
        for doc in documents(kb_id):
            if doc["status"] != "ready":
                continue
            for topic in doc["topics"]:
                grouped.setdefault(topic, []).append({"id": doc["id"], "name": doc["name"]})
        return [
            {"label": topic, "documents": docs}
            for topic, docs in sorted(grouped.items(), key=lambda pair: (-len(pair[1]), pair[0]))
        ]

    @app.get("/api/knowledge-bases/{kb_id}/graph")
    def graph(kb_id: str):
        kb = get_kb(kb_id)
        cached = store.one("SELECT * FROM graphs WHERE kb_id=?", (kb_id,))
        if cached:
            result = json.loads(cached["payload"])
            result["updated_at"] = cached["updated_at"]
        else:
            raw_docs = store.all("SELECT * FROM documents WHERE kb_id=?", (kb_id,))
            result = local_graph(raw_docs, all_chunks(kb_id))
        return {**result, "status": kb["graph_status"], "error": kb["graph_error"]}

    @app.post("/api/knowledge-bases/{kb_id}/graph/import")
    async def import_graph(kb_id: str, file: Annotated[UploadFile, File()]):
        get_kb(kb_id)
        blob = await file.read(5 * 1024 * 1024 + 1)
        await file.close()
        if len(blob) > 5 * 1024 * 1024:
            raise HTTPException(413, "Graph JSON exceeds 5 MB.")
        try:
            payload = json.loads(blob)
            graph = normalize_graph(payload, documents(kb_id), all_chunks(kb_id))
        except (ValueError, UnicodeDecodeError) as exc:
            raise HTTPException(422, str(exc)) from exc
        store.save_graph(kb_id, graph)
        return graph

    @app.delete("/api/knowledge-bases/{kb_id}/graph/import", status_code=204)
    def reset_graph(kb_id: str):
        get_kb(kb_id)
        store.execute("DELETE FROM graphs WHERE kb_id=?", (kb_id,))
        store.execute(
            "UPDATE knowledge_bases SET graph_status='',graph_error='' WHERE id=?", (kb_id,)
        )

    def require_graph_api(kb):
        if kb["backend"] != "ragflow" or not settings.legacy_graph_api:
            raise HTTPException(
                422,
                "Build a Graph artifact in RAGFlow and import its JSON. "
                "For legacy servers, enable RAGFLOW_LEGACY_GRAPH_API in .env.",
            )

    @app.post("/api/knowledge-bases/{kb_id}/graph/build", status_code=202)
    def build_graph(kb_id: str):
        kb = get_kb(kb_id)
        require_graph_api(kb)
        result = rag.build_graph(kb["dataset_id"])
        store.execute(
            "UPDATE knowledge_bases SET graph_status='processing',graph_error='' WHERE id=?",
            (kb_id,),
        )
        return {"status": "processing", "task": result}

    @app.post("/api/knowledge-bases/{kb_id}/graph/sync")
    def sync_graph(kb_id: str):
        kb = get_kb(kb_id)
        require_graph_api(kb)
        try:
            status = (
                rag.graph_status(kb["dataset_id"]) if kb["graph_status"] == "processing" else {}
            )
            if isinstance(status, dict) and status.get("progress") is not None:
                progress = float(status["progress"])
                if progress < 0:
                    raise RAGFlowError(
                        "Graph construction failed: " + str(status.get("progress_msg", ""))[:400]
                    )
                if progress < 1:
                    return {"status": "processing", "progress": progress}
            payload = rag.graph(kb["dataset_id"])
            result = normalize_graph(
                payload or {}, documents(kb_id), all_chunks(kb_id), origin="ragflow"
            )
            if not result["nodes"]:
                return {
                    "status": "processing" if kb["graph_status"] == "processing" else "empty",
                    "message": "No graph available yet. Finish construction in RAGFlow first.",
                }
            store.save_graph(kb_id, result)
            return {"status": "ready", "nodes": len(result["nodes"])}
        except (RAGFlowError, ValueError) as exc:
            store.execute(
                "UPDATE knowledge_bases SET graph_status='failed',graph_error=? WHERE id=?",
                (str(exc), kb_id),
            )
            if isinstance(exc, ValueError):
                raise HTTPException(502, "Invalid RAGFlow graph: " + str(exc)) from exc
            raise

    @app.post("/api/knowledge-bases/{kb_id}/search")
    def search(kb_id: str, body: Query):
        kb = get_kb(kb_id)
        if kb["backend"] == "local":
            return {"mode": "keyword", "results": search_chunks(body.question, all_chunks(kb_id))}
        raw = rag.retrieve(kb["dataset_id"], body.question)
        results = []
        for chunk in raw:
            doc = store.one(
                "SELECT id,name FROM documents WHERE kb_id=? AND remote_id=?",
                (kb_id, chunk.get("document_id", chunk.get("doc_id"))),
            )
            results.append(
                {
                    "id": chunk.get("id"),
                    "doc_id": doc["id"] if doc else None,
                    "document_name": doc["name"]
                    if doc
                    else chunk.get("document_name", chunk.get("docnm_kwd", "RAGFlow source")),
                    "content": plain_text(
                        chunk.get("content", chunk.get("content_with_weight", ""))
                    ),
                    "score": chunk.get("similarity", 0),
                    "page": None,
                }
            )
        return {"mode": "semantic", "results": results}

    dist = ROOT / "dist"
    if dist.exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/", include_in_schema=False)
    def index():
        if not (dist / "index.html").exists():
            raise HTTPException(503, "Build the frontend first: npm install && npm run build")
        return FileResponse(dist / "index.html")

    return app


app = create_app()
