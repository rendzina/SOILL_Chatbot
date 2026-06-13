"""
Chat orchestration: RAG answer, citation filtering, and conversation logging.

**Created:** 07-06-2026 (UK style).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Sequence

from .. import config as cfg
from ..citations import sources_cited_in_answer, split_suggested_questions
from ..chat_history import ChatTurn
from ..conversation_log import log_interaction
from ..rag import SourceRef, answer_question
from ..user_identity import ClientMetadata


@dataclass
class ChatSource:
    label: int
    chunk_id: str
    source_path: str
    filename: str
    location_type: str
    location_start: int
    location_end: int
    preview: str


@dataclass
class ChatResponse:
    answer: str
    sources: list[ChatSource]
    top_k: int
    suggested_questions: list[str] | None = None
    error: str | None = None


def _source_ref_to_chat_source(source: SourceRef) -> ChatSource:
    path = source.source_path or ""
    return ChatSource(
        label=source.label,
        chunk_id=source.chunk_id,
        source_path=path,
        filename=os.path.basename(path) if path else "unknown",
        location_type=source.location_type,
        location_start=source.location_start,
        location_end=source.location_end,
        preview=source.preview,
    )


class ChatService:
    """Process user queries via RAG and return structured responses."""

    def chat(
        self,
        message: str,
        *,
        history: Sequence[ChatTurn] | None = None,
        client: ClientMetadata | None = None,
        top_k: int | None = None,
    ) -> ChatResponse:
        text = (message or "").strip()
        if not text:
            return ChatResponse(answer="", sources=[], top_k=int(top_k or cfg.RAG_TOP_K))

        k = int(top_k or cfg.RAG_TOP_K)
        try:
            result = answer_question(text, top_k=k, history=history)
        except (FileNotFoundError, RuntimeError) as exc:
            log_interaction(question=text, answer=None, error=str(exc), client=client)
            return ChatResponse(
                answer=str(exc),
                sources=[],
                top_k=k,
                error=str(exc),
            )
        except Exception as exc:
            log_interaction(question=text, answer=None, error=str(exc), client=client)
            return ChatResponse(
                answer=f"An unexpected error occurred: {exc}",
                sources=[],
                top_k=k,
                error=str(exc),
            )

        answer_text, suggested = split_suggested_questions(result.answer)
        cited = sources_cited_in_answer(answer_text, result.sources)
        chat_sources = [_source_ref_to_chat_source(s) for s in cited]

        log_interaction(
            question=text,
            answer=answer_text,
            cited_sources_count=len(chat_sources),
            client=client,
        )

        return ChatResponse(
            answer=answer_text,
            sources=chat_sources,
            top_k=result.top_k,
            suggested_questions=suggested,
        )
