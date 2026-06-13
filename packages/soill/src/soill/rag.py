"""
RAG: retrieve with pgvector, answer with Mistral chat only.

Retrieval optionally applies MMR on a larger candidate pool from Postgres.

**Created:** 04-06-2026 (UK style).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Optional, Sequence, Union

import numpy as np
from mistralai import Mistral
from mistralai.models import AssistantMessage, SystemMessage, UserMessage

from . import config as cfg
from . import embeddings as emb
from . import store_pg
from .chat_history import ChatTurn

SYSTEM_RAG = (
    "You are the SOILL public assistant for the EU Mission Soil Living Labs and "
    "Lighthouses programme. You help users understand living labs, lighthouses, "
    "and soil health innovation from start to scale. "
    "Answer only using the numbered context excerpts below. If the answer is not "
    "in the context, say you do not have enough information. "
    "Cite only context you actually rely on: place markers such as [1] or [2, 3] "
    "immediately next to the sentences they support. Use numeric markers only inside "
    "brackets—do not add page numbers or paragraph symbols inside the brackets "
    "(e.g. write [1], not [1, p. 3]). "
    "Structure longer answers with Markdown: use ### only for a short section heading "
    "(never #### or deeper). For lists use `- **Short title:** explanation [1]` — "
    "do not prefix list items with #### or numbered headings like `1.` inside markdown "
    "heading markers. Use blank lines between paragraphs. "
    "Where you cite, weave in the source file name and location (pages, lines, or "
    "paragraphs) in that same sentence or the next short phrase—do not add a separate "
    "closing section that lists every context number or reprints all filenames. "
    "The chat interface's expandable source list shows only excerpts whose numbers "
    "you cite in the answer text. "
    "Earlier user and assistant turns may be included for follow-up questions only; "
    "interpret pronouns such as \"that\" or \"those\" from the prior turn when answering. "
    "Ground every factual claim in the numbered context excerpts, not in chat history alone. "
    "Use UK English spelling in your answers. "
    "After the main answer, append exactly three concise follow-up questions the user "
    "might ask next. Put them in this block (no citations inside the block):\n"
    "<<SUGGESTED>>\n"
    "- First follow-up question?\n"
    "- Second follow-up question?\n"
    "- Third follow-up question?\n"
    "<<END>>"
)

_FOLLOWUP_HINTS = frozenset({
    "that", "those", "this", "these", "them", "they", "it", "its",
    "above", "mentioned", "same", "involve", "involves",
})


@dataclass
class SourceRef:
    label: int
    chunk_id: str
    source_path: str
    location_type: str
    location_start: int
    location_end: int
    preview: str


@dataclass
class RAGResult:
    answer: str
    sources: list[SourceRef]
    top_k: int


def _mmr_indices(sim_q: np.ndarray, v_mat: np.ndarray, k: int, lam: float) -> list[int]:
    m = int(v_mat.shape[0])
    if m <= k:
        return list(range(m))
    lam_f = float(lam)
    selected = [int(np.argmax(sim_q))]
    remaining = set(range(m)) - set(selected)
    s_block = v_mat @ v_mat.T
    while len(selected) < k and remaining:
        best_j = -1
        best_score = -np.inf
        for j in remaining:
            red = max(float(s_block[j, s]) for s in selected)
            score = lam_f * float(sim_q[j]) - (1.0 - lam_f) * red
            if score > best_score:
                best_score = score
                best_j = int(j)
        selected.append(best_j)
        remaining.remove(best_j)
    return selected


def _deduped_chunk_ids_from_hits(
    hits: list[dict],
) -> tuple[list[str], dict[str, dict]]:
    chunk_ids: list[str] = []
    by_id: dict[str, dict] = {}
    seen: set[str] = set()
    for h in hits:
        cid = str(h["chunk_id"])
        if cid in seen:
            continue
        seen.add(cid)
        chunk_ids.append(cid)
        by_id[cid] = h
    return chunk_ids, by_id


def _assistant_content_to_str(content: Union[str, list, None]) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    out: list[str] = []
    for part in content:
        t = getattr(part, "text", None)
        if t:
            out.append(t)
    return "".join(out)


def retrieve(
    client: Mistral, question: str, top_k: int
) -> tuple[list[SourceRef], str]:
    n_vec = store_pg.count_chunks()
    if not n_vec:
        raise FileNotFoundError(
            "No indexed chunks in the database. Add source files to "
            "SourceDocuments/ and run `uv run soill-process` from your machine."
        )

    qv = emb.embed_query(client, question)
    q_flat = np.asarray(qv, dtype=np.float32).reshape(-1)

    use_mmr = bool(cfg.RAG_MMR_ENABLED) and top_k >= 2 and n_vec >= 2
    if use_mmr:
        fetch_k = min(
            n_vec,
            max(top_k * int(cfg.RAG_MMR_FETCH_MULT), top_k + 1),
            int(cfg.RAG_MMR_FETCH_CAP),
        )
    else:
        fetch_k = min(n_vec, top_k)

    hits = store_pg.search_similar(q_flat, fetch_k)
    chunk_ids_order, hit_by_id = _deduped_chunk_ids_from_hits(hits)
    if not chunk_ids_order:
        return [], ""

    ch_ids_unique: list[str]
    if use_mmr and len(chunk_ids_order) > top_k:
        try:
            v_mat = np.vstack(
                [hit_by_id[cid]["embedding"] for cid in chunk_ids_order]
            )
            sim_q = v_mat @ q_flat
            pick = _mmr_indices(sim_q, v_mat, top_k, float(cfg.RAG_MMR_LAMBDA))
            ch_ids_unique = [chunk_ids_order[i] for i in pick]
        except Exception:
            try:
                v_mat = store_pg.fetch_embeddings_matrix_ordered(chunk_ids_order)
                sim_q = v_mat @ q_flat
                pick = _mmr_indices(sim_q, v_mat, top_k, float(cfg.RAG_MMR_LAMBDA))
                ch_ids_unique = [chunk_ids_order[i] for i in pick]
            except Exception:
                ch_ids_unique = chunk_ids_order[:top_k]
    else:
        ch_ids_unique = chunk_ids_order[: min(top_k, len(chunk_ids_order))]

    rows = store_pg.fetch_chunks_by_ids(ch_ids_unique)
    sources: list[SourceRef] = []
    context_lines: list[str] = []
    for n, r in enumerate(rows, start=1):
        sp = r.get("source_path", "unknown")
        loc_type = str(r.get("location_type", "page"))
        p0 = int(r.get("location_start", r.get("page_start", 0)))
        p1 = int(r.get("location_end", r.get("page_end", 0)))
        text = (r.get("text") or "").strip()
        preview = text[:280] + ("…" if len(text) > 280 else "")
        sources.append(
            SourceRef(
                label=n,
                chunk_id=str(r.get("chunk_id", "")),
                source_path=str(sp),
                location_type=loc_type,
                location_start=p0,
                location_end=p1,
                preview=preview,
            )
        )
        base = os.path.basename(str(sp)) if sp else "unknown"
        label = _format_location_label(loc_type, p0, p1)
        context_lines.append(f"[{n}] (source file: {base}, {label}):\n{text}\n")
    return sources, "\n\n".join(context_lines)


def _format_location_label(location_type: str, start: int, end: int) -> str:
    plural = {
        "page": "pages",
        "line": "lines",
        "paragraph": "paragraphs",
    }.get(location_type, "locations")
    return f"{plural} {start}–{end}"


def _is_follow_up_question(question: str) -> bool:
    tokens = {token.strip(".,?!") for token in question.lower().split()}
    if tokens & _FOLLOWUP_HINTS:
        return True
    return len(question.split()) < 10


def _retrieval_query(
    user_message: str,
    history: Optional[Sequence[ChatTurn]],
) -> str:
    if not cfg.CHAT_HISTORY_ENABLED or not cfg.CHAT_HISTORY_EXPAND_RETRIEVAL:
        return user_message
    if not history:
        return user_message

    prior_questions = [
        turn.question.strip() for turn in history if turn.question.strip()
    ]
    if not prior_questions:
        return user_message

    if not _is_follow_up_question(user_message):
        return user_message

    combined = " ".join(prior_questions + [user_message.strip()])
    max_len = cfg.CHAT_HISTORY_RETRIEVAL_MAX_CHARS
    if len(combined) > max_len:
        combined = combined[-max_len:]
    return combined


def _build_chat_messages(
    user_block: str,
    history: Optional[Sequence[ChatTurn]],
) -> list:
    messages: list = [SystemMessage(content=SYSTEM_RAG)]
    if history:
        for turn in history:
            messages.append(UserMessage(content=turn.question))
            messages.append(AssistantMessage(content=turn.answer))
    messages.append(UserMessage(content=user_block))
    return messages


def answer_question(
    user_message: str,
    top_k: Optional[int] = None,
    history: Optional[Sequence[ChatTurn]] = None,
) -> RAGResult:
    k = int(top_k or cfg.RAG_TOP_K)
    client: Mistral = emb.get_client()
    search_query = _retrieval_query(user_message, history)
    sources, context_block = retrieve(client, search_query, k)
    if not context_block:
        return RAGResult(
            answer=(
                "I do not have any indexed documents to search. Add source files to "
                "SourceDocuments/, then run `uv run soill-process` while connected to "
                "the database."
            ),
            sources=[],
            top_k=k,
        )
    user_block = f"Question: {user_message}\n\nContext:\n{context_block}"
    messages = _build_chat_messages(user_block, history)
    chat = client.chat.complete(
        model=cfg.MISTRAL_CHAT_MODEL,
        messages=messages,  # type: ignore[arg-type]
        temperature=0.2,
    )
    if not chat or not chat.choices:
        return RAGResult(answer="No response from the model.", sources=sources, top_k=k)
    content = chat.choices[0].message.content  # type: ignore[union-attr, index]
    text = _assistant_content_to_str(content)
    return RAGResult(answer=text.strip(), sources=sources, top_k=k)
