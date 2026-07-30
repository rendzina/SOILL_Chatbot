"""
SOILL Public RAG Chatbot — FastAPI HTTP API.

Run from repo root:
  uv run --directory apps/api uvicorn main:app --reload --port 8080

**Created:** 07-06-2026 (UK style).
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response

from routes.chat import router as chat_router

logger = logging.getLogger(__name__)


class ShortCacheStaticFiles(StaticFiles):
    """Force browsers to revalidate chat UI assets after each deploy."""

    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        if isinstance(response, Response) and path.endswith((".js", ".css", ".html")):
            response.headers["Cache-Control"] = "no-cache, must-revalidate"
        return response


_DEFAULT_ORIGINS = [
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
]

_extra_origins = [
    origin.strip()
    for origin in os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Run retention purge once on startup (Render has no built-in cron)."""
    try:
        from soill.conversation_log import purge_expired_conversations

        deleted = purge_expired_conversations()
        logger.info("Startup conversation retention purge removed %s row(s)", deleted)
    except Exception as exc:
        logger.warning("Startup conversation retention purge skipped: %s", exc)
    yield


app = FastAPI(
    title="SOILL Chatbot API",
    description="HTTP API for the SOILL public RAG assistant.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_DEFAULT_ORIGINS + _extra_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)

_web_dir = Path(__file__).resolve().parents[2] / "web"
if _web_dir.is_dir():
    app.mount(
        "/web",
        ShortCacheStaticFiles(directory=str(_web_dir), html=True),
        name="web",
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
