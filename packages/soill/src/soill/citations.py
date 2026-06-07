"""
Parse numeric citation markers from RAG assistant answers.

**Created:** 07-06-2026 (UK style).
"""

from __future__ import annotations

import re

from .rag import SourceRef


def sources_cited_in_answer(answer: str, sources: list[SourceRef]) -> list[SourceRef]:
    """
    Keep only context labels that appear as numeric citations in the answer
    (e.g. [1], [2, 3]). Matches how the model is instructed to cite in SYSTEM_RAG.
    """
    if not sources:
        return []
    max_label = max(s.label for s in sources)
    cited: set[int] = set()
    for m in re.finditer(r"\[([^\]]+)\]", answer or ""):
        for part in m.group(1).split(","):
            p = part.strip()
            if p.isdigit():
                n = int(p)
                if 1 <= n <= max_label:
                    cited.add(n)
    by_label = {s.label: s for s in sources}
    return [by_label[i] for i in sorted(cited) if i in by_label]
