"""
Chat API routes.

**Created:** 07-06-2026 (UK style).
"""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from soill import config as cfg
from soill.conversation_log import fetch_recent_turns
from soill.services import ChatService, ChatSource
from soill.user_identity import metadata_from_environ

router = APIRouter(prefix="/api", tags=["chat"])

chat_service = ChatService()


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    session_id: Optional[str] = None


class ChatSourceResponse(BaseModel):
    label: int
    chunk_id: str
    filename: str
    source_path: str
    location_type: str
    location_start: int
    location_end: int
    preview: str


class ChatResponseBody(BaseModel):
    answer: str
    sources: list[ChatSourceResponse]
    session_id: str
    error: Optional[str] = None


def _to_source_response(source: ChatSource) -> ChatSourceResponse:
    return ChatSourceResponse(
        label=source.label,
        chunk_id=source.chunk_id,
        filename=source.filename,
        source_path=source.source_path,
        location_type=source.location_type,
        location_start=source.location_start,
        location_end=source.location_end,
        preview=source.preview,
    )


def _request_environ(request: Request) -> dict:
    scope = request.scope
    headers = request.headers
    environ = {
        "REMOTE_ADDR": scope.get("client", ("", 0))[0] if scope.get("client") else "",
        "HTTP_USER_AGENT": headers.get("user-agent", ""),
        "HTTP_X_FORWARDED_FOR": headers.get("x-forwarded-for", ""),
        "X-Forwarded-For": headers.get("x-forwarded-for", ""),
    }
    return environ


@router.post("/chat", response_model=ChatResponseBody)
async def chat(request: Request, body: ChatRequest) -> ChatResponseBody:
    session_id = (body.session_id or "").strip() or str(uuid.uuid4())
    client = metadata_from_environ(
        thread_id=session_id,
        session_id=session_id,
        environ=_request_environ(request),
        client_type="api",
    )

    history = []
    if cfg.CHAT_HISTORY_ENABLED:
        history = fetch_recent_turns(session_id)

    response = chat_service.chat(
        body.message.strip(),
        history=history,
        client=client,
    )

    return ChatResponseBody(
        answer=response.answer,
        sources=[_to_source_response(s) for s in response.sources],
        session_id=session_id,
        error=response.error,
    )
