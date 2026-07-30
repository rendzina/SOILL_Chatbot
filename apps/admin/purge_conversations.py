#!/usr/bin/env python3
"""
Delete conversation rows older than CONVERSATION_RETENTION_DAYS (default 365).

Run from repo root:
  uv run soill-purge-conversations

**Created:** 30-07-2026 (UK style).
"""

from __future__ import annotations

import argparse
import sys

from soill import config as cfg
from soill.conversation_log import purge_expired_conversations


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Purge expired SOILL conversation log rows."
    )
    parser.add_argument(
        "--days",
        type=int,
        default=None,
        help=(
            "Retention window in days (default: CONVERSATION_RETENTION_DAYS "
            f"env / config, currently {cfg.CONVERSATION_RETENTION_DAYS}). "
            "Use 0 to skip deletion."
        ),
    )
    args = parser.parse_args()
    days = cfg.CONVERSATION_RETENTION_DAYS if args.days is None else args.days
    if days <= 0:
        print("Retention purge disabled (days <= 0).", file=sys.stderr)
        return 0
    deleted = purge_expired_conversations(days)
    print(
        f"Deleted {deleted} conversation(s) older than {days} day(s).",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
