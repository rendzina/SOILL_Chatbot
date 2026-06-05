"""
SOILL Public RAG Chatbot — Chainlit web UI.

Run from repo root: uv run --directory apps/chatbot chainlit run app.py

**Created:** 04-06-2026 (UK style).
**Credits:** Professor Stephen Hallett, Cranfield University, 2026.
"""

from __future__ import annotations

import os
import re
import uuid

import chainlit as cl


@cl.data_layer
def _soill_data_layer():
    """
    Disable Chainlit's built-in Postgres layer (requires asyncpg).

    SOILL persists chats via soill.conversation_log → soill_conversations using
    DATABASE_URL and psycopg, not Chainlit's ChainlitDataLayer.
    """
    return None


from soill import config as cfg
from soill.chat_history import ChatTurn, append_turn, trim_history
from soill.conversation_log import fetch_recent_turns, log_interaction
from soill.rag import SourceRef, answer_question
from soill.user_identity import metadata_from_chainlit, metadata_to_dict

_SESSION_SOURCES_PREFIX = "rag_sources_"
_SESSION_HISTORY_KEY = "chat_history"
_ASSISTANT_NAME = "SOILL"


def _sources_cited_in_answer(answer: str, sources: list[SourceRef]) -> list[SourceRef]:
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


def _get_session_history() -> list[ChatTurn]:
    raw = cl.user_session.get(_SESSION_HISTORY_KEY)
    if not raw:
        return []
    return [ChatTurn(question=item["question"], answer=item["answer"]) for item in raw]


def _set_session_history(turns: list[ChatTurn]) -> None:
    cl.user_session.set(
        _SESSION_HISTORY_KEY,
        [{"question": turn.question, "answer": turn.answer} for turn in turns],
    )


@cl.on_chat_start
async def on_chat_start() -> None:
    client_meta = metadata_from_chainlit()
    cl.user_session.set("client_metadata", metadata_to_dict(client_meta))

    if (
        cfg.CHAT_HISTORY_ENABLED
        and cfg.LOG_CONVERSATIONS
        and client_meta.thread_id != "anonymous"
    ):
        prior = fetch_recent_turns(client_meta.thread_id)
        _set_session_history(trim_history(prior))

    # First assistant message in the thread (edit the text below as needed).
    await cl.Message(
        author=_ASSISTANT_NAME,
        content=(
            "I am the **SOILL** chatbot. I can help you find the information you need relating to the EU Mission Soil Living Labs and Lighthouses, from start to scale. "
            "Please ask me a question and I will do my best to help you and point you in the right direction to the information you need."
        ),
    ).send()

    if not cfg.MISTRAL_API_KEY:
        await cl.Message(
            author=_ASSISTANT_NAME,
            content=(
                "Set `MISTRAL_API_KEY` in your `.env` at the project root, then restart."
            ),
        ).send()


@cl.action_callback("show_sources")
async def on_show_sources(action: cl.Action) -> None:
    sid = (action.payload or {}).get("sid")
    if not sid or not isinstance(sid, str):
        await cl.Message(
            author=_ASSISTANT_NAME,
            content="Could not load sources (missing reference).",
        ).send()
        return
    text = cl.user_session.get(f"{_SESSION_SOURCES_PREFIX}{sid}")
    if not text:
        await cl.Message(
            author=_ASSISTANT_NAME,
            content="Sources for this answer are no longer available. Ask again to refresh.",
        ).send()
        return
    await cl.Message(author=_ASSISTANT_NAME, content=text).send()


def _sources_block(cited_only: list[SourceRef]) -> str:
    if not cited_only:
        return ""
    lines: list[str] = ["**Sources (cited)**\n"]
    for s in cited_only:
        name = os.path.basename(s.source_path) if s.source_path else "unknown"
        preview = re.sub(r"\s+", " ", s.preview)
        label = f"{s.location_type}s {s.location_start}–{s.location_end}"
        lines.append(f"- **[{s.label}]** `{name}` — {label}: {preview}\n")
    return "".join(lines)


@cl.on_message
async def on_message(message: cl.Message) -> None:
    text = (message.content or "").strip()
    if not text:
        return

    client_meta = metadata_from_chainlit()
    cl.user_session.set("client_metadata", metadata_to_dict(client_meta))
    history = _get_session_history() if cfg.CHAT_HISTORY_ENABLED else []

    try:
        result = answer_question(text, top_k=cfg.RAG_TOP_K, history=history)
    except (FileNotFoundError, RuntimeError) as e:
        log_interaction(question=text, answer=None, error=str(e), client=client_meta)
        await cl.Message(author=_ASSISTANT_NAME, content=str(e)).send()
        return
    except Exception as e:
        log_interaction(question=text, answer=None, error=str(e), client=client_meta)
        await cl.Message(
            author=_ASSISTANT_NAME,
            content=f"An unexpected error occurred: {e}",
        ).send()
        return

    cited_sources = _sources_cited_in_answer(result.answer, result.sources)
    sources = _sources_block(cited_sources)
    actions: list[cl.Action] = []
    if sources:
        sid = str(uuid.uuid4())
        cl.user_session.set(f"{_SESSION_SOURCES_PREFIX}{sid}", sources)
        n = len(cited_sources)
        actions.append(
            cl.Action(
                name="show_sources",
                payload={"sid": sid},
                label=f"Show cited sources ({n})",
                tooltip="Opens the cited source list for this answer in the chat.",
            )
        )

    await cl.Message(
        author=_ASSISTANT_NAME,
        content=result.answer,
        actions=actions,
    ).send()

    if cfg.CHAT_HISTORY_ENABLED and result.answer:
        updated = append_turn(history, text, result.answer)
        _set_session_history(updated)

    log_interaction(
        question=text,
        answer=result.answer,
        cited_sources_count=len(cited_sources),
        client=client_meta,
    )
