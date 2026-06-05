"""Extract text from PDFs with a page label for each word (citations)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

import fitz  # PyMuPDF


@dataclass
class PageText:
    page_num: int  # 1-based
    text: str


def extract_pages(pdf_path: Path) -> List[PageText]:
    """Return each page's text in reading order (best effort)."""
    doc = fitz.open(pdf_path)
    try:
        pages: List[PageText] = []
        for i in range(len(doc)):
            t = doc.load_page(i).get_text("text")
            t = t.strip() if t else ""
            pages.append(PageText(page_num=i + 1, text=t))
    finally:
        doc.close()
    return pages


def words_with_pages(pages: List[PageText]) -> Tuple[List[str], List[int]]:
    """
    Split the document into word tokens, each token tagged with its 1-based page.
    """
    words: List[str] = []
    per_page: List[int] = []
    for p in pages:
        for w in p.text.split():
            if w:
                words.append(w)
                per_page.append(p.page_num)
    return words, per_page
