#!/usr/bin/env python3
"""Apply sql/001_init.sql to the database configured in DATABASE_URL."""

from __future__ import annotations

import sys

from soill import config as cfg
from soill import store_pg


def main() -> int:
    try:
        store_pg.init_schema()
    except Exception as exc:
        print(f"Schema initialisation failed: {exc}", file=sys.stderr)
        return 1
    print(f"Schema applied from {cfg.SQL_INIT_PATH}", file=sys.stderr)
    try:
        store_pg.ping_database()
        print("Database connection OK.", file=sys.stderr)
    except Exception as exc:
        print(f"Connection check failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
