"""
Parse numeric citation markers from RAG assistant answers.

**Created:** 07-06-2026 (UK style).
"""

from __future__ import annotations

import re

from .rag import SourceRef

_SUGGESTED_BLOCK = re.compile(
    r"<<SUGGESTED>>\s*(.*?)\s*<<END>>\s*$",
    re.DOTALL | re.IGNORECASE,
)


def split_suggested_questions(answer: str) -> tuple[str, list[str]]:
    """
    Separate the main answer from an optional <<SUGGESTED>>…<<END>> block.
    Returns at most three follow-up questions for the UI.
    """
    text = (answer or "").strip()
    if not text:
        return "", []

    match = _SUGGESTED_BLOCK.search(text)
    if not match:
        return text, []

    main_answer = text[: match.start()].strip()
    block = match.group(1).strip()
    questions: list[str] = []

    for line in block.splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue
        if cleaned.startswith("- "):
            cleaned = cleaned[2:].strip()
        elif cleaned.startswith("* "):
            cleaned = cleaned[2:].strip()
        else:
            cleaned = re.sub(r"^\d+\.\s+", "", cleaned)
        if cleaned:
            questions.append(cleaned)

    return main_answer, questions[:3]


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
