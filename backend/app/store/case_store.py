"""One case's database and files: data/cases/<id>/case.db, files/, pages/ (ADR-0001).

A CaseStore only ever sees its own folder. Everything that reads case content (retrieval,
agents, tools) is handed one CaseStore and nothing else.
"""

import json
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from app.contracts.analysis import (
    CONFLICT_STATUSES,
    CONFLICT_TYPES,
    EFFECTS,
    ELEMENT_KINDS,
    ELEMENT_STATUSES,
    JOB_STATUSES,
    PARTY_ROLES,
    SEVERITIES,
)
from app.contracts.documents import (
    DOCUMENT_KINDS,
    DOCUMENT_STATUSES,
    BBox,
    ChunkView,
    Document,
    DocumentKind,
    DocumentStatus,
    PageDetail,
    SourceRef,
)
from app.contracts.usage import RoleUsage, UsageSummary


def _in(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


# Append-only: each entry upgrades the schema by one version (tracked in PRAGMA user_version).
MIGRATIONS = [
    f"""
    CREATE TABLE documents (
        id TEXT PRIMARY KEY,
        filename TEXT NOT NULL,
        kind TEXT NOT NULL CHECK (kind IN ({_in(DOCUMENT_KINDS)})),
        sha256 TEXT NOT NULL UNIQUE,
        status TEXT NOT NULL CHECK (status IN ({_in(DOCUMENT_STATUSES)})),
        n_pages INTEGER NOT NULL DEFAULT 0,
        error TEXT
    );
    CREATE TABLE pages (
        doc_id TEXT NOT NULL REFERENCES documents(id),
        page_no INTEGER NOT NULL,
        text TEXT NOT NULL,
        ocr INTEGER NOT NULL,
        PRIMARY KEY (doc_id, page_no)
    );
    CREATE TABLE chunks (
        id INTEGER PRIMARY KEY,
        doc_id TEXT NOT NULL REFERENCES documents(id),
        page_no INTEGER NOT NULL,
        bbox TEXT,
        text TEXT NOT NULL,
        embedding BLOB NOT NULL
    );
    CREATE VIRTUAL TABLE chunks_fts USING fts5(
        text, content='chunks', content_rowid='id', tokenize='porter unicode61'
    );
    """,
    # v2: one row per LLM call; trace_id links the row to its Phoenix trace (ADR-0004).
    """
    CREATE TABLE llm_calls (
        id INTEGER PRIMARY KEY,
        created_at TEXT NOT NULL,
        role TEXT NOT NULL,
        model TEXT NOT NULL,
        prompt TEXT NOT NULL,
        prompt_version TEXT NOT NULL,
        job_id TEXT,
        session_id TEXT,
        input_tokens INTEGER NOT NULL,
        output_tokens INTEGER NOT NULL,
        cost_usd REAL,
        latency_ms INTEGER NOT NULL,
        trace_id TEXT NOT NULL
    );
    """,
    # v3: analysis results (Stage 4). Replaced as a whole by each successful analysis run.
    f"""
    CREATE TABLE jobs (
        id TEXT PRIMARY KEY,
        kind TEXT NOT NULL,
        status TEXT NOT NULL CHECK (status IN ({_in(JOB_STATUSES)})),
        step TEXT NOT NULL,
        progress REAL NOT NULL,
        error TEXT,
        started_at TEXT NOT NULL,
        finished_at TEXT
    );
    CREATE TABLE parties (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        role TEXT NOT NULL CHECK (role IN ({_in(PARTY_ROLES)}))
    );
    CREATE TABLE claims (
        id INTEGER PRIMARY KEY,
        speaker TEXT NOT NULL,
        aspect TEXT NOT NULL,
        statement TEXT NOT NULL,
        when_iso TEXT,
        chunk_id INTEGER NOT NULL REFERENCES chunks(id),
        quote TEXT NOT NULL,
        verified INTEGER NOT NULL
    );
    CREATE TABLE conflicts (
        id INTEGER PRIMARY KEY,
        aspect TEXT NOT NULL,
        type TEXT NOT NULL CHECK (type IN ({_in(CONFLICT_TYPES)})),
        severity TEXT NOT NULL CHECK (severity IN ({_in(SEVERITIES)})),
        effect TEXT NOT NULL CHECK (effect IN ({_in(EFFECTS)})),
        explanation TEXT NOT NULL,
        status TEXT NOT NULL CHECK (status IN ({_in(CONFLICT_STATUSES)})),
        claim_ids TEXT NOT NULL
    );
    CREATE TABLE elements (
        id INTEGER PRIMARY KEY,
        kind TEXT NOT NULL CHECK (kind IN ({_in(ELEMENT_KINDS)})),
        element TEXT NOT NULL,
        status TEXT NOT NULL CHECK (status IN ({_in(ELEMENT_STATUSES)})),
        explanation TEXT NOT NULL,
        citations TEXT NOT NULL
    );
    CREATE TABLE adverse (
        id INTEGER PRIMARY KEY,
        explanation TEXT NOT NULL,
        citations TEXT NOT NULL
    );
    CREATE TABLE issues (
        id INTEGER PRIMARY KEY,
        title TEXT NOT NULL,
        our_argument TEXT NOT NULL,
        opposing_argument TEXT NOT NULL,
        rebuttal TEXT NOT NULL,
        cross_questions TEXT NOT NULL,
        citations TEXT NOT NULL
    );
    """,
]


_SETUP_LOCK = threading.Lock()


@dataclass
class ParsedChunk:
    page_no: int
    text: str
    bbox: BBox | None


@dataclass
class ParsedPage:
    page_no: int
    text: str
    ocr: bool


@dataclass
class LLMCall:
    role: str
    model: str
    prompt: str
    prompt_version: str
    input_tokens: int
    output_tokens: int
    cost_usd: float | None  # None = provider could not price it (not the same as free)
    latency_ms: int
    trace_id: str
    job_id: str | None = None
    session_id: str | None = None


class CaseStore:
    def __init__(self, case_dir: Path) -> None:
        self.dir = case_dir
        self.files_dir = case_dir / "files"
        self.pages_dir = case_dir / "pages"
        self.files_dir.mkdir(parents=True, exist_ok=True)
        self.pages_dir.mkdir(exist_ok=True)
        self.db = sqlite3.connect(case_dir / "case.db", check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        # Concurrent requests open the same case at once. Switching to WAL and migrating both need
        # an exclusive lock, so one thread does them while the others wait (one server process
        # per data dir is assumed; this lock does not span processes).
        with _SETUP_LOCK:
            self.db.execute("PRAGMA journal_mode=WAL")  # API reads while an ingest job writes
            self._migrate()

    def _migrate(self) -> None:
        """Apply pending migrations. Called under _SETUP_LOCK: the version must be read inside
        the lock, or two threads both apply the same migration."""
        version = self.db.execute("PRAGMA user_version").fetchone()[0]
        for i, sql in enumerate(MIGRATIONS[version:], start=version + 1):
            with self.db:
                self.db.executescript(sql)
                self.db.execute(f"PRAGMA user_version = {i}")

    def close(self) -> None:
        self.db.close()

    # --- documents -------------------------------------------------------------------------

    def add_document(self, filename: str, kind: DocumentKind, sha256: str) -> Document:
        doc = Document(
            id=uuid.uuid4().hex, filename=filename, kind=kind, status="queued", n_pages=0
        )
        with self.db:
            self.db.execute(
                "INSERT INTO documents (id, filename, kind, sha256, status) VALUES (?, ?, ?, ?, ?)",
                (doc.id, filename, kind, sha256, doc.status),
            )
        return doc

    def find_by_sha(self, sha256: str) -> Document | None:
        row = self.db.execute("SELECT * FROM documents WHERE sha256 = ?", (sha256,)).fetchone()
        return _to_doc(row) if row else None

    def get_document(self, doc_id: str) -> Document | None:
        row = self.db.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
        return _to_doc(row) if row else None

    def list_documents(self) -> list[Document]:
        rows = self.db.execute("SELECT * FROM documents ORDER BY filename").fetchall()
        return [_to_doc(r) for r in rows]

    def set_status(self, doc_id: str, status: DocumentStatus, error: str | None = None) -> None:
        with self.db:
            self.db.execute(
                "UPDATE documents SET status = ?, error = ? WHERE id = ?", (status, error, doc_id)
            )

    def file_path(self, doc: Document) -> Path:
        return self.files_dir / f"{doc.id}{Path(doc.filename).suffix.lower()}"

    def page_image_path(self, doc_id: str, page_no: int) -> Path:
        return self.pages_dir / f"{doc_id}_{page_no}.png"

    # --- ingest output -----------------------------------------------------------------------

    def save_ingest(
        self,
        doc_id: str,
        pages: list[ParsedPage],
        chunks: list[ParsedChunk],
        embeddings: np.ndarray,
    ) -> None:
        """Write a whole document's pages + chunks in one transaction, then mark it ready."""
        assert len(chunks) == len(embeddings)
        with self.db:
            self.db.executemany(
                "INSERT INTO pages VALUES (?, ?, ?, ?)",
                [(doc_id, p.page_no, p.text, int(p.ocr)) for p in pages],
            )
            for c, vec in zip(chunks, embeddings.astype(np.float32), strict=True):
                bbox = json.dumps(c.bbox) if c.bbox else None
                cur = self.db.execute(
                    "INSERT INTO chunks (doc_id, page_no, bbox, text, embedding) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (doc_id, c.page_no, bbox, c.text, vec.tobytes()),
                )
                self.db.execute(
                    "INSERT INTO chunks_fts (rowid, text) VALUES (?, ?)", (cur.lastrowid, c.text)
                )
            self.db.execute(
                "UPDATE documents SET status = 'ready', n_pages = ?, error = NULL WHERE id = ?",
                (len(pages), doc_id),
            )

    # --- reads ------------------------------------------------------------------------------

    def get_page(self, doc_id: str, page_no: int) -> PageDetail | None:
        doc = self.get_document(doc_id)
        row = self.db.execute(
            "SELECT * FROM pages WHERE doc_id = ? AND page_no = ?", (doc_id, page_no)
        ).fetchone()
        if not doc or not row:
            return None
        chunks = self.db.execute(
            "SELECT id, bbox, text FROM chunks WHERE doc_id = ? AND page_no = ? ORDER BY id",
            (doc_id, page_no),
        ).fetchall()
        return PageDetail(
            doc_id=doc_id,
            page=page_no,
            n_pages=doc.n_pages,
            ocr=bool(row["ocr"]),
            text=row["text"],
            chunks=[ChunkView(id=c["id"], bbox=_bbox(c["bbox"]), text=c["text"]) for c in chunks],
        )

    def embeddings(self) -> tuple[np.ndarray, np.ndarray]:
        """All chunk ids and their embedding matrix for this case (small: one case only)."""
        rows = self.db.execute("SELECT id, embedding FROM chunks").fetchall()
        if not rows:
            return np.zeros(0, dtype=np.int64), np.zeros((0, 0), dtype=np.float32)
        ids = np.array([r["id"] for r in rows], dtype=np.int64)
        return ids, np.vstack([np.frombuffer(r["embedding"], dtype=np.float32) for r in rows])

    def fts(self, match: str, limit: int) -> list[int]:
        rows = self.db.execute(
            "SELECT rowid FROM chunks_fts WHERE chunks_fts MATCH ? ORDER BY rank LIMIT ?",
            (match, limit),
        ).fetchall()
        return [r[0] for r in rows]

    # --- LLM usage ---------------------------------------------------------------------------

    def record_llm_call(self, call: LLMCall) -> None:
        with self.db:
            self.db.execute(
                "INSERT INTO llm_calls (created_at, role, model, prompt, prompt_version, job_id, "
                "session_id, input_tokens, output_tokens, cost_usd, latency_ms, trace_id) "
                "VALUES (datetime('now'), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (call.role, call.model, call.prompt, call.prompt_version, call.job_id,
                 call.session_id, call.input_tokens, call.output_tokens, call.cost_usd,
                 call.latency_ms, call.trace_id),
            )  # fmt: skip

    def usage_summary(self) -> UsageSummary:
        rows = self.db.execute(
            "SELECT role, model, COUNT(*) AS calls, SUM(input_tokens) AS input_tokens, "
            "SUM(output_tokens) AS output_tokens, COALESCE(SUM(cost_usd), 0) AS cost_usd, "
            "SUM(cost_usd IS NULL) AS unpriced_calls FROM llm_calls GROUP BY role, model "
            "ORDER BY role"
        ).fetchall()
        by_role = [RoleUsage(**dict(r)) for r in rows]
        return UsageSummary(
            calls=sum(r.calls for r in by_role),
            input_tokens=sum(r.input_tokens for r in by_role),
            output_tokens=sum(r.output_tokens for r in by_role),
            cost_usd=sum(r.cost_usd for r in by_role),
            by_role=by_role,
        )

    def doc_chunks(self, doc_id: str) -> list[tuple[int, int, str]]:
        """(chunk_id, page, text) for one document, in reading order."""
        rows = self.db.execute(
            "SELECT id, page_no, text FROM chunks WHERE doc_id = ? ORDER BY page_no, id", (doc_id,)
        ).fetchall()
        return [(r[0], r[1], r[2]) for r in rows]

    def chunk_texts(self) -> dict[int, str]:
        return {r[0]: r[1] for r in self.db.execute("SELECT id, text FROM chunks")}

    def chunks_by_id(self, ids: list[int]) -> dict[int, tuple[SourceRef, str]]:
        if not ids:
            return {}
        marks = ",".join("?" * len(ids))
        rows = self.db.execute(
            "SELECT c.id, c.doc_id, c.page_no, c.bbox, c.text, d.filename FROM chunks c "
            f"JOIN documents d ON d.id = c.doc_id WHERE c.id IN ({marks})",
            ids,
        ).fetchall()
        return {
            r["id"]: (
                SourceRef(chunk_id=r["id"], doc_id=r["doc_id"], filename=r["filename"],
                          page=r["page_no"], bbox=_bbox(r["bbox"])),
                r["text"],
            )
            for r in rows
        }  # fmt: skip


def _bbox(raw: str | None) -> BBox | None:
    if raw is None:
        return None
    x0, y0, x1, y1 = json.loads(raw)
    return (x0, y0, x1, y1)


def _to_doc(row: sqlite3.Row) -> Document:
    return Document(
        id=row["id"],
        filename=row["filename"],
        kind=row["kind"],
        status=row["status"],
        n_pages=row["n_pages"],
        error=row["error"],
    )
