"""
Log user questions and assistant answers to PostgreSQL.

**Created:** 04-06-2026 (UK style).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, List, Optional, Union

from . import config as cfg
from . import store_pg
from .chat_history import ChatTurn
from .user_identity import ClientMetadata, coerce_client_metadata

logger = logging.getLogger(__name__)


def fetch_recent_turns(thread_id: str, limit: Optional[int] = None) -> List[ChatTurn]:
    """Load the latest completed Q&A turns for a Chainlit thread (newest last)."""
    if not cfg.LOG_CONVERSATIONS or not thread_id or thread_id == "anonymous":
        return []
    turn_limit = limit if limit is not None else cfg.CHAT_HISTORY_TURNS
    if turn_limit <= 0:
        return []

    try:
        rows = store_pg.fetch_recent_turns_from_db(thread_id, turn_limit)
        return [
            ChatTurn(question=row["question"], answer=row["answer"]) for row in rows
        ]
    except Exception as exc:
        logger.warning("Failed to load conversation history: %s", exc)
        return []


def log_interaction(
    *,
    question: str,
    answer: Optional[str] = None,
    error: Optional[str] = None,
    cited_sources_count: int = 0,
    rag_top_k: Optional[int] = None,
    client: Union[ClientMetadata, dict[str, Any], None] = None,
) -> None:
    """Insert one row per question. Does not raise: failures are logged only."""
    if not cfg.LOG_CONVERSATIONS:
        return
    if not question.strip():
        return

    meta = coerce_client_metadata(client)
    doc: dict[str, Any] = {
        "created_at": datetime.now(timezone.utc),
        "thread_id": meta.thread_id,
        "session_id": meta.session_id,
        "visitor_fingerprint": meta.visitor_fingerprint,
        "client_type": meta.client_type,
        "question": question,
        "answer": answer,
        "error": error,
        "cited_sources_count": cited_sources_count,
        "rag_top_k": rag_top_k if rag_top_k is not None else cfg.RAG_TOP_K,
        "chat_model": cfg.MISTRAL_CHAT_MODEL,
        "embed_model": cfg.MISTRAL_EMBED_MODEL,
        "client_ip": None,
        "user_agent": None,
        "forwarded_for": None,
    }
    if cfg.LOG_CLIENT_METADATA:
        doc["client_ip"] = meta.client_ip or None
        doc["user_agent"] = meta.user_agent or None
        doc["forwarded_for"] = meta.forwarded_for or None

    try:
        row_id = store_pg.insert_conversation(doc)
        logger.info(
            "Logged conversation to %s (id=%s, thread_id=%s)",
            cfg.SOILL_CONVERSATIONS_TABLE,
            row_id,
            meta.thread_id,
        )
    except Exception as exc:
        logger.error(
            "Failed to log conversation to %s: %s",
            cfg.SOILL_CONVERSATIONS_TABLE,
            exc,
            exc_info=True,
        )
