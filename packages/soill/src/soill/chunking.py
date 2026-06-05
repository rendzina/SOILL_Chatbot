"""Word-based text chunking with fixed overlap (prototype defaults)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import List

from . import config as cfg


@dataclass
class TextChunk:
    """One slice of a source document, ready to embed and store."""

    chunk_index: int
    text: str
    page_start: int
    page_end: int
    chunk_id: str


def stable_chunk_id(source_path: str, file_hash: str, chunk_index: int) -> str:
    """Deterministic id so Postgres rows stay stable across re-ingest."""
    raw = f"{source_path}\0{file_hash}\0{chunk_index}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def chunk_text_with_page_labels(
    words: List[str],
    word_pages: List[int],
    source_path: str,
    file_hash: str,
) -> list[TextChunk]:
    """
    Build overlapping word windows: ~500 words, 20% overlap, stride 400.
    `word_pages` must align 1:1 with `words` (page number of each word).
    """
    if not words or len(words) != len(word_pages):
        return []

    size = cfg.CHUNK_SIZE_WORDS
    stride = cfg.CHUNK_STRIDE_WORDS
    if stride <= 0 or size <= 0:
        return []

    chunks: list[TextChunk] = []
    start = 0
    idx = 0
    n = len(words)
    while start < n:
        end = min(start + size, n)
        wslice = words[start:end]
        pslice = word_pages[start:end]
        p_start = pslice[0] if pslice else 1
        p_end = pslice[-1] if pslice else p_start
        text = " ".join(wslice).strip()
        if text:
            chk_id = stable_chunk_id(source_path, file_hash, idx)
            chunks.append(
                TextChunk(
                    chunk_index=idx,
                    text=text,
                    page_start=int(p_start),
                    page_end=int(p_end),
                    chunk_id=chk_id,
                )
            )
            idx += 1
        if end >= n:
            break
        start += stride
    return chunks
