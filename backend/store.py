import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4


def uid() -> str:
    return uuid4().hex


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, directory):
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / "knowledge.sqlite3"
        self.files = directory / "files"
        self.files.mkdir(exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS knowledge_bases (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL,
                    backend TEXT NOT NULL, dataset_id TEXT, created_at TEXT NOT NULL,
                    graph_status TEXT NOT NULL DEFAULT '', graph_error TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY, kb_id TEXT NOT NULL REFERENCES knowledge_bases(id),
                    name TEXT NOT NULL, size INTEGER NOT NULL, status TEXT NOT NULL,
                    progress REAL NOT NULL DEFAULT 0, error TEXT NOT NULL DEFAULT '',
                    remote_id TEXT, created_at TEXT NOT NULL, topics TEXT NOT NULL DEFAULT '[]'
                );
                CREATE TABLE IF NOT EXISTS chunks (
                    id TEXT PRIMARY KEY, doc_id TEXT NOT NULL REFERENCES documents(id)
                    ON DELETE CASCADE, ordinal INTEGER NOT NULL, content TEXT NOT NULL,
                    page INTEGER, remote_id TEXT, keywords TEXT NOT NULL DEFAULT '[]'
                );
                CREATE INDEX IF NOT EXISTS docs_kb ON documents(kb_id);
                CREATE INDEX IF NOT EXISTS chunks_doc ON chunks(doc_id);
                CREATE TABLE IF NOT EXISTS graphs (
                    kb_id TEXT PRIMARY KEY REFERENCES knowledge_bases(id),
                    payload TEXT NOT NULL, updated_at TEXT NOT NULL
                );
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def one(self, query, args=()):
        with self.connect() as db:
            row = db.execute(query, args).fetchone()
            return dict(row) if row else None

    def all(self, query, args=()):
        with self.connect() as db:
            return [dict(row) for row in db.execute(query, args).fetchall()]

    def execute(self, query, args=()):
        with self.connect() as db:
            db.execute(query, args)

    def add_kb(self, name, description, backend="local", dataset_id=None):
        kb_id = uid()
        self.execute(
            "INSERT INTO knowledge_bases (id,name,description,backend,dataset_id,created_at) "
            "VALUES (?,?,?,?,?,?)",
            (kb_id, name, description, backend, dataset_id, now()),
        )
        return self.one("SELECT * FROM knowledge_bases WHERE id=?", (kb_id,))

    def add_document(self, kb_id, name, blob, remote_id=None):
        doc_id = uid()
        self.execute(
            "INSERT INTO documents (id,kb_id,name,size,status,remote_id,created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (doc_id, kb_id, name, len(blob), "queued", remote_id, now()),
        )
        try:
            (self.files / doc_id).write_bytes(blob)
        except OSError:
            self.execute("DELETE FROM documents WHERE id=?", (doc_id,))
            raise
        return self.one("SELECT * FROM documents WHERE id=?", (doc_id,))

    def save_chunks(self, doc_id, chunks, topics):
        with self.connect() as db:
            db.execute("DELETE FROM chunks WHERE doc_id=?", (doc_id,))
            for i, chunk in enumerate(chunks):
                db.execute(
                    "INSERT INTO chunks VALUES (?,?,?,?,?,?,?)",
                    (
                        uid(),
                        doc_id,
                        i + 1,
                        chunk["content"],
                        chunk.get("page"),
                        chunk.get("remote_id"),
                        json.dumps(chunk.get("keywords", [])),
                    ),
                )
            db.execute(
                "UPDATE documents SET status='ready',progress=1,error='',topics=? WHERE id=?",
                (json.dumps(topics), doc_id),
            )

    def save_graph(self, kb_id, graph):
        self.execute(
            "INSERT INTO graphs VALUES (?,?,?) ON CONFLICT(kb_id) DO UPDATE SET "
            "payload=excluded.payload,updated_at=excluded.updated_at",
            (kb_id, json.dumps(graph), now()),
        )
        self.execute(
            "UPDATE knowledge_bases SET graph_status='ready',graph_error='' WHERE id=?",
            (kb_id,),
        )
