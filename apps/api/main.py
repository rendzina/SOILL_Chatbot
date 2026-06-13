"""
SOILL Public RAG Chatbot — FastAPI HTTP API.

Run from repo root:
  uv run --directory apps/api uvicorn main:app --reload --port 8080

**Created:** 07-06-2026 (UK style).
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from routes.chat import router as chat_router

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

app = FastAPI(
    title="SOILL Chatbot API",
    description="HTTP API for the SOILL public RAG assistant.",
    version="0.1.0",
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
    app.mount("/web", StaticFiles(directory=str(_web_dir), html=True), name="web")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
