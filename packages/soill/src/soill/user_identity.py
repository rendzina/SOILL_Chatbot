"""
Derive visitor metadata from Chainlit session / WSGI environ (for logging).

IP addresses and user-agent strings are not stored. The visitor_fingerprint
column is retained for schema compatibility and is always set to a constant
anonymous placeholder.

**Created:** 04-06-2026 (UK style).
**Updated:** 31-07-2026 — stop storing IP-derived identifiers.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from typing import Any, Optional, Union

logger = logging.getLogger(__name__)

# Column is NOT NULL; use a constant so we never persist IP/UA-derived hashes.
ANONYMOUS_FINGERPRINT = "anonymous"


@dataclass(frozen=True)
class ClientMetadata:
    """Identifiers for a chat client (browser session or CLI)."""

    thread_id: str
    session_id: str
    visitor_fingerprint: str
    client_ip: str
    user_agent: str
    client_type: str
    forwarded_for: str = ""

    @staticmethod
    def anonymous() -> ClientMetadata:
        return ClientMetadata(
            thread_id="anonymous",
            session_id="anonymous",
            visitor_fingerprint=ANONYMOUS_FINGERPRINT,
            client_ip="",
            user_agent="",
            client_type="unknown",
        )


def metadata_from_environ(
    *,
    thread_id: str,
    session_id: str,
    environ: Optional[dict[str, Any]],
    client_type: str = "webapp",
) -> ClientMetadata:
    """Build client metadata without capturing IP or user-agent."""
    _ = environ  # retained for call-site compatibility; not used for identity
    return ClientMetadata(
        thread_id=thread_id or session_id or "anonymous",
        session_id=session_id or thread_id or "anonymous",
        visitor_fingerprint=ANONYMOUS_FINGERPRINT,
        client_ip="",
        user_agent="",
        client_type=client_type or "webapp",
        forwarded_for="",
    )


def metadata_from_chainlit() -> ClientMetadata:
    """Read client metadata from the active Chainlit request context."""
    try:
        from chainlit.context import get_context

        session = get_context().session
        thread_id = str(session.thread_id or session.id or "")
        session_id = str(session.id or thread_id or "")
        environ = getattr(session, "environ", None)
        client_type = str(getattr(session, "client_type", "webapp") or "webapp")
        if not thread_id and not session_id:
            logger.warning(
                "Chainlit session has no thread_id or id; using anonymous metadata"
            )
            return ClientMetadata.anonymous()
        return metadata_from_environ(
            thread_id=thread_id,
            session_id=session_id,
            environ=environ if isinstance(environ, dict) else None,
            client_type=client_type,
        )
    except Exception as exc:
        logger.warning("Could not read Chainlit session metadata: %s", exc)
        return ClientMetadata.anonymous()


def metadata_to_dict(meta: ClientMetadata) -> dict[str, str]:
    return asdict(meta)


def coerce_client_metadata(
    value: Union[ClientMetadata, dict[str, Any], None],
) -> ClientMetadata:
    if value is None:
        return ClientMetadata.anonymous()
    if isinstance(value, ClientMetadata):
        return ClientMetadata(
            thread_id=value.thread_id,
            session_id=value.session_id,
            visitor_fingerprint=ANONYMOUS_FINGERPRINT,
            client_ip="",
            user_agent="",
            client_type=value.client_type,
            forwarded_for="",
        )
    if isinstance(value, dict):
        return ClientMetadata(
            thread_id=str(
                value.get("thread_id") or value.get("session_id") or "anonymous"
            ),
            session_id=str(
                value.get("session_id") or value.get("thread_id") or "anonymous"
            ),
            visitor_fingerprint=ANONYMOUS_FINGERPRINT,
            client_ip="",
            user_agent="",
            client_type=str(value.get("client_type") or "webapp"),
            forwarded_for="",
        )
    return ClientMetadata.anonymous()
