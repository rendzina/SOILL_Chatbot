"""Extract words and location labels from supported source file types."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

from docx import Document

from . import pdf_extract


@dataclass
class SourceWords:
    """Normalised words and integer locations from one source document."""

    source_type: str
    location_type: str  # page | paragraph | line
    words: List[str]
    locations: List[int]


def extract_source_words(path: Path) -> SourceWords:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _extract_pdf(path)
    if suffix == ".docx":
        return _extract_docx(path)
    if suffix == ".txt":
        return _extract_txt(path)
    raise ValueError(f"Unsupported source type: {suffix}")


def _extract_pdf(path: Path) -> SourceWords:
    pages = pdf_extract.extract_pages(path)
    words, page_numbers = pdf_extract.words_with_pages(pages)
    return SourceWords(
        source_type="pdf",
        location_type="page",
        words=words,
        locations=page_numbers,
    )


def _extract_docx(path: Path) -> SourceWords:
    doc = Document(path)
    words: list[str] = []
    locations: list[int] = []
    for idx, para in enumerate(doc.paragraphs, start=1):
        text = (para.text or "").strip()
        if not text:
            continue
        for w in text.split():
            if w:
                words.append(w)
                locations.append(idx)
    return SourceWords(
        source_type="docx",
        location_type="paragraph",
        words=words,
        locations=locations,
    )


def _extract_txt(path: Path) -> SourceWords:
    text = _read_txt(path)
    words: list[str] = []
    locations: list[int] = []
    for idx, line in enumerate(text.splitlines(), start=1):
        clean = line.strip()
        if not clean:
            continue
        for w in clean.split():
            if w:
                words.append(w)
                locations.append(idx)
    return SourceWords(
        source_type="txt",
        location_type="line",
        words=words,
        locations=locations,
    )


def _read_txt(path: Path) -> str:
    for enc in ("utf-8", "cp1252"):
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")
