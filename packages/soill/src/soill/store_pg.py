"""PostgreSQL + pgvector access for chunks, documents, and conversations."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import psycopg
from pgvector.psycopg import register_vector
from psycopg import sql
from psycopg.rows import dict_row

from . import config as cfg

logger = logging.getLogger(__name__)

_conn: Optional[psycopg.Connection] = None
_conn_url: Optional[str] = None


class DatabaseError(RuntimeError):
    """Raised when DATABASE_URL is missing or the database is unreachable."""


def _require_database_url() -> str:
    url = (cfg.DATABASE_URL or "").strip()
    if not url:
        raise DatabaseError(
            "DATABASE_URL is not set. Add it to .env (Render Postgres connection string)."
        )
    return url


def get_connection() -> psycopg.Connection:
    """Return a shared connection; reconnect if DATABASE_URL changed."""
    global _conn, _conn_url
    url = _require_database_url()
    if _conn is None or _conn.closed or _conn_url != url:
        if _conn is not None and not _conn.closed:
            _conn.close()
        _conn = psycopg.connect(url, row_factory=dict_row)
        register_vector(_conn)
        _conn_url = url
    return _conn


def ping_database() -> None:
    conn = get_connection()
    conn.execute("SELECT 1")


def run_sql_file(path: Path) -> None:
    """Execute a SQL file (statements split on semicolons)."""
    text = path.read_text(encoding="utf-8")
    statements = [s.strip() for s in text.split(";") if s.strip()]
    conn = get_connection()
    for stmt in statements:
        conn.execute(stmt)
    conn.commit()


def init_schema() -> None:
    """Apply sql/001_init.sql idempotently."""
    if not cfg.SQL_INIT_PATH.is_file():
        raise FileNotFoundError(f"Schema file not found: {cfg.SQL_INIT_PATH}")
    run_sql_file(cfg.SQL_INIT_PATH)


def count_chunks() -> int:
    conn = get_connection()
    row = conn.execute("SELECT COUNT(*) AS n FROM chunks").fetchone()
    return int(row["n"]) if row else 0


def count_document_rows() -> int:
    conn = get_connection()
    row = conn.execute("SELECT COUNT(*) AS n FROM documents").fetchone()
    return int(row["n"]) if row else 0


def clear_ingestion_tables() -> tuple[int, int]:
    """Delete all chunk and document rows. Returns (chunks, documents)."""
    conn = get_connection()
    ch = conn.execute("DELETE FROM chunks").rowcount
    doc = conn.execute("DELETE FROM documents").rowcount
    conn.commit()
    return int(ch or 0), int(doc or 0)


def delete_chunks_for_path(source_path: str) -> int:
    conn = get_connection()
    cur = conn.execute(
        "DELETE FROM chunks WHERE source_path = %s",
        (source_path,),
    )
    conn.commit()
    return int(cur.rowcount or 0)


def upsert_document_record(
    source_path: str, file_hash: str, status: str = "indexed"
) -> None:
    now = datetime.now(timezone.utc)
    conn = get_connection()
    conn.execute(
            """
            INSERT INTO documents (source_path, file_hash, last_processed, status)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (source_path) DO UPDATE SET
                file_hash = EXCLUDED.file_hash,
                last_processed = EXCLUDED.last_processed,
                status = EXCLUDED.status
            """,
            (source_path, file_hash, now, status),
        )
    conn.commit()


def remove_document_record(source_path: str) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM documents WHERE source_path = %s", (source_path,))
    conn.commit()


def insert_chunk_rows(rows: List[Dict[str, Any]]) -> None:
    if not rows:
        return
    sql_insert = """
        INSERT INTO chunks (
            chunk_id, source_path, source_hash, chunk_index, text,
            page_start, page_end, source_type, location_type,
            location_start, location_end, embedding, created_at
        ) VALUES (
            %(chunk_id)s, %(source_path)s, %(source_hash)s, %(chunk_index)s,
            %(text)s, %(page_start)s, %(page_end)s, %(source_type)s,
            %(location_type)s, %(location_start)s, %(location_end)s,
            %(embedding)s, %(created_at)s
        )
        ON CONFLICT (chunk_id) DO UPDATE SET
            source_path = EXCLUDED.source_path,
            source_hash = EXCLUDED.source_hash,
            chunk_index = EXCLUDED.chunk_index,
            text = EXCLUDED.text,
            page_start = EXCLUDED.page_start,
            page_end = EXCLUDED.page_end,
            source_type = EXCLUDED.source_type,
            location_type = EXCLUDED.location_type,
            location_start = EXCLUDED.location_start,
            location_end = EXCLUDED.location_end,
            embedding = EXCLUDED.embedding,
            created_at = EXCLUDED.created_at
    """
    conn = get_connection()
    with conn.cursor() as cur:
        cur.executemany(sql_insert, rows)
    conn.commit()


def fetch_chunks_by_ids(chunk_ids: List[str]) -> List[Dict[str, Any]]:
    if not chunk_ids:
        return []
    conn = get_connection()
    cur = conn.execute(
        "SELECT * FROM chunks WHERE chunk_id = ANY(%s)",
        (chunk_ids,),
    )
    by = {str(r["chunk_id"]): r for r in cur.fetchall()}
    return [by[cid] for cid in chunk_ids if cid in by]


def _row_to_embedding(row: Dict[str, Any]) -> np.ndarray:
    emb = row.get("embedding")
    if emb is None:
        raise KeyError("Missing embedding on chunk row")
    if isinstance(emb, np.ndarray):
        return emb.astype("float32").reshape(-1)
    return np.asarray(emb, dtype="float32").reshape(-1)


def search_similar(
    query_vector: np.ndarray, fetch_k: int
) -> List[Dict[str, Any]]:
    """
    Cosine-distance search on L2-normalised embeddings.

    Returns rows with chunk_id, similarity (1 - distance), and embedding array.
    """
    q = np.asarray(query_vector, dtype="float32").reshape(-1)
    conn = get_connection()
    cur = conn.execute(
        """
        SELECT
            chunk_id,
            1 - (embedding <=> %s::vector) AS similarity,
            embedding
        FROM chunks
        ORDER BY embedding <=> %s::vector
        LIMIT %s
        """,
        (q.tolist(), q.tolist(), int(fetch_k)),
    )
    hits: List[Dict[str, Any]] = []
    for row in cur.fetchall():
        hits.append(
            {
                "chunk_id": str(row["chunk_id"]),
                "similarity": float(row["similarity"]),
                "embedding": _row_to_embedding(row),
            }
        )
    return hits


def fetch_embeddings_matrix_ordered(chunk_ids: Sequence[str]) -> np.ndarray:
    if not chunk_ids:
        return np.zeros((0, 0), dtype="float32")
    rows = fetch_chunks_by_ids(list(chunk_ids))
    if len(rows) != len(chunk_ids):
        raise KeyError("Missing one or more chunk embeddings")
    return np.vstack([_row_to_embedding(r) for r in rows])


def insert_conversation(doc: Dict[str, Any]) -> int:
    table = sql.Identifier(cfg.SOILL_CONVERSATIONS_TABLE)
    query = sql.SQL(
        """
        INSERT INTO {table} (
            created_at, thread_id, session_id, visitor_fingerprint,
            client_type, question, answer, error, cited_sources_count,
            rag_top_k, chat_model, embed_model, client_ip, user_agent,
            forwarded_for
        ) VALUES (
            %(created_at)s, %(thread_id)s, %(session_id)s,
            %(visitor_fingerprint)s, %(client_type)s, %(question)s,
            %(answer)s, %(error)s, %(cited_sources_count)s, %(rag_top_k)s,
            %(chat_model)s, %(embed_model)s, %(client_ip)s, %(user_agent)s,
            %(forwarded_for)s
        ) RETURNING id
        """
    ).format(table=table)
    conn = get_connection()
    row = conn.execute(query, doc).fetchone()
    conn.commit()
    return int(row["id"]) if row else 0


def fetch_conversations(
    date_from: Optional[Any] = None,
    date_to: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """Return conversation rows sorted by created_at ascending."""
    clauses: list[str] = []
    params: list[Any] = []
    if date_from is not None:
        clauses.append("created_at >= %s")
        params.append(date_from)
    if date_to is not None:
        clauses.append("created_at <= %s")
        params.append(date_to)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    table = cfg.SOILL_CONVERSATIONS_TABLE
    conn = get_connection()
    cur = conn.execute(
        f"SELECT * FROM {table}{where} ORDER BY created_at ASC",
        params,
    )
    return list(cur.fetchall())


def fetch_recent_turns_from_db(thread_id: str, limit: int) -> List[Dict[str, str]]:
    table = cfg.SOILL_CONVERSATIONS_TABLE
    conn = get_connection()
    cur = conn.execute(
        f"""
        SELECT question, answer
        FROM {table}
        WHERE thread_id = %s
          AND answer IS NOT NULL
          AND TRIM(answer) <> ''
          AND (error IS NULL OR TRIM(error) = '')
        ORDER BY created_at DESC
        LIMIT %s
        """,
        (thread_id, limit),
    )
    rows = list(cur.fetchall())
    rows.reverse()
    return [
        {"question": str(r["question"]), "answer": str(r["answer"])}
        for r in rows
        if r.get("question") and r.get("answer")
    ]
