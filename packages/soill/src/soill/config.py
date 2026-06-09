"""
Load configuration from the environment and sensible defaults.

Includes RAG, conversation logging, and multi-turn chat settings.

**Created:** 04-06-2026 (UK style).
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


def repo_root() -> Path:
    """Monorepo root (contains pyproject.toml and packages/)."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file() and (parent / "packages").is_dir():
            return parent
    return here.parents[4]


_ROOT = repo_root()
load_dotenv(_ROOT / ".env")

SOURCE_DOCUMENTS: Path = Path(
    os.environ.get("SOURCE_DOCUMENTS", str(_ROOT / "SourceDocuments"))
)
PDF_PREPROCESSING_ROOT: Path = Path(
    os.environ.get("PDF_PREPROCESSING_ROOT", str(_ROOT / "PDFPreProcessing"))
)
OCR_INCOMING_DIR: Path = PDF_PREPROCESSING_ROOT / "IncomingScans"
OCR_OUTPUT_DIR: Path = PDF_PREPROCESSING_ROOT / "OCR_Output"
OCR_FAILED_DIR: Path = PDF_PREPROCESSING_ROOT / "OCR_Failed"
OCR_LOGS_DIR: Path = PDF_PREPROCESSING_ROOT / "OCR_Processing" / "Logs"
OCR_BATCH_SUMMARY_LOG: Path = OCR_LOGS_DIR / "batch-summary.log"
OCR_LANGUAGE: str = os.environ.get("OCR_LANGUAGE", "eng").strip() or "eng"

DATA_DIR: Path = _ROOT / "data"
MANIFEST_PATH: Path = DATA_DIR / "manifest.json"
SQL_INIT_PATH: Path = _ROOT / "sql" / "001_init.sql"
REPORTS_DIR: Path = _ROOT / "Reports"

DATABASE_URL: str = os.environ.get("DATABASE_URL", "")
MISTRAL_API_KEY: str = os.environ.get("MISTRAL_API_KEY", "")
MISTRAL_EMBED_MODEL: str = os.environ.get("MISTRAL_EMBED_MODEL", "mistral-embed")
MISTRAL_CHAT_MODEL: str = os.environ.get("MISTRAL_CHAT_MODEL", "mistral-small-latest")
RAG_TOP_K: int = int(os.environ.get("RAG_TOP_K", "8"))

EMBEDDING_DIMENSION: int = int(os.environ.get("EMBEDDING_DIMENSION", "1024"))
SOILL_CONVERSATIONS_TABLE: str = "soill_conversations"


def _env_bool(key: str, default: bool) -> bool:
    v = os.environ.get(key)
    if v is None or v.strip() == "":
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


LOG_CONVERSATIONS: bool = _env_bool("LOG_CONVERSATIONS", True)
LOG_CLIENT_METADATA: bool = _env_bool("LOG_CLIENT_METADATA", True)

CHAT_HISTORY_ENABLED: bool = _env_bool("CHAT_HISTORY_ENABLED", True)
CHAT_HISTORY_TURNS: int = max(0, int(os.environ.get("CHAT_HISTORY_TURNS", "3")))
CHAT_HISTORY_MAX_ANSWER_CHARS: int = max(
    200, int(os.environ.get("CHAT_HISTORY_MAX_ANSWER_CHARS", "1500"))
)
CHAT_HISTORY_EXPAND_RETRIEVAL: bool = _env_bool("CHAT_HISTORY_EXPAND_RETRIEVAL", True)
CHAT_HISTORY_RETRIEVAL_MAX_CHARS: int = max(
    400, int(os.environ.get("CHAT_HISTORY_RETRIEVAL_MAX_CHARS", "2000"))
)

RAG_MMR_ENABLED: bool = _env_bool("RAG_MMR_ENABLED", True)
RAG_MMR_LAMBDA: float = min(
    1.0, max(0.0, float(os.environ.get("RAG_MMR_LAMBDA", "0.58")))
)
RAG_MMR_FETCH_MULT: int = min(8, max(2, int(os.environ.get("RAG_MMR_FETCH_MULT", "3"))))
RAG_MMR_FETCH_CAP: int = min(64, max(12, int(os.environ.get("RAG_MMR_FETCH_CAP", "40"))))

OCR_FORCE: bool = _env_bool("OCR_FORCE", False)

SUPPORTED_SOURCE_EXTENSIONS: tuple[str, ...] = (".pdf", ".docx", ".txt")

CHUNK_SIZE_WORDS: int = 500
CHUNK_OVERLAP_WORDS: int = 100
CHUNK_STRIDE_WORDS: int = CHUNK_SIZE_WORDS - CHUNK_OVERLAP_WORDS

EMBED_BATCH_SIZE: int = 32
