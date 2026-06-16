#!/usr/bin/env python3
"""
Sync public source URLs from data/source_catalog.json into Postgres.

Edit the JSON when a document is published (e.g. on Zenodo), then run:

  uv run soill-source-catalog

Rebuild the JSON skeleton from all ingested documents (keeps existing URLs):

  uv run soill-source-catalog --init-from-db

Preview changes without writing to the database:

  uv run soill-source-catalog --dry-run

**Created:** 10-06-2026 (UK style).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from soill import config as cfg
from soill import store_pg

_D5_1_PDF = (
    "Classification of Soil Living Labs and Soil Lighthouses/"
    "D5.1_Methodological framework for Soil Health LLs and LHs monitoring and "
    "evaluation_V1.1.pdf"
)
_D5_1_ZENODO = {
    "title": (
        "D5.1 - Methodological framework for Soil Health LLs and LHs "
        "monitoring and evaluation"
    ),
    "is_public": True,
    "public_url": "https://zenodo.org/records/18466509",
}


def _normalise_entry(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {"is_public": False}
    is_public = bool(raw.get("is_public", False))
    public_url = (raw.get("public_url") or "").strip() or None
    title = (raw.get("title") or "").strip() or None
    if is_public and not public_url:
        raise ValueError("is_public is true but public_url is missing")
    return {
        "title": title,
        "is_public": is_public,
        "public_url": public_url if is_public else None,
    }


def _load_catalog(path: Path) -> dict[str, dict[str, Any]]:
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    sources = data.get("sources") or {}
    if not isinstance(sources, dict):
        raise ValueError(f"{path}: 'sources' must be an object")
    return {str(k): _normalise_entry(v) for k, v in sources.items()}


def _save_catalog(path: Path, sources: dict[str, dict[str, Any]]) -> None:
    cfg.DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "updated_utc": datetime.now(timezone.utc).isoformat(),
        "notes": (
            "Keys must match documents.source_path exactly. Set is_public and "
            "public_url for published documents (e.g. Zenodo). Re-run "
            "uv run soill-source-catalog after edits."
        ),
        "sources": dict(sorted(sources.items())),
    }
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def _default_entry(source_path: str) -> dict[str, Any]:
    if source_path == _D5_1_PDF:
        return dict(_D5_1_ZENODO)
    return {"title": None, "is_public": False, "public_url": None}


def init_catalog_from_db(path: Path) -> int:
    store_pg.apply_source_catalog_schema()
    db_paths = store_pg.list_document_paths()
    existing = _load_catalog(path) if path.is_file() else {}
    sources: dict[str, dict[str, Any]] = {}
    for source_path in db_paths:
        if source_path in existing:
            sources[source_path] = existing[source_path]
        else:
            sources[source_path] = _default_entry(source_path)
    _save_catalog(path, sources)
    public_count = sum(1 for entry in sources.values() if entry.get("is_public"))
    print(
        f"Wrote {path} with {len(sources)} document(s) "
        f"({public_count} public).",
        file=sys.stderr,
    )
    return 0


def sync_catalog_to_db(path: Path, *, dry_run: bool) -> int:
    if not path.is_file():
        print(
            f"Catalog not found: {path}\n"
            "Run: uv run soill-source-catalog --init-from-db",
            file=sys.stderr,
        )
        return 1

    sources = _load_catalog(path)
    if not sources:
        print(f"No entries in {path}", file=sys.stderr)
        return 1

    if not dry_run:
        store_pg.apply_source_catalog_schema()

    db_paths = set(store_pg.list_document_paths())
    unknown = sorted(set(sources) - db_paths)
    if unknown:
        print("Warning: catalog paths not in database (skipped):", file=sys.stderr)
        for item in unknown:
            print(f"  - {item}", file=sys.stderr)

    missing_from_catalog = sorted(db_paths - set(sources))
    if missing_from_catalog:
        print(
            "Note: ingested documents missing from catalog "
            "(run --init-from-db to add):",
            file=sys.stderr,
        )
        for item in missing_from_catalog:
            print(f"  - {item}", file=sys.stderr)

    updated = 0
    for source_path, entry in sorted(sources.items()):
        if source_path not in db_paths:
            continue
        title = entry.get("title")
        public_url = entry.get("public_url")
        is_public = bool(entry.get("is_public"))
        if dry_run:
            print(
                f"[dry-run] {source_path}\n"
                f"  is_public={is_public}\n"
                f"  public_url={public_url or '(none)'}\n"
                f"  title={title or '(none)'}",
                file=sys.stderr,
            )
            updated += 1
            continue
        if store_pg.update_document_metadata(
            source_path,
            title=title,
            public_url=public_url,
            is_public=is_public,
        ):
            updated += 1

    action = "Would update" if dry_run else "Updated"
    print(f"{action} {updated} document row(s) in Postgres.", file=sys.stderr)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Manage public source URLs in data/source_catalog.json"
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        default=cfg.SOURCE_CATALOG_PATH,
        help=f"Catalog JSON path (default: {cfg.SOURCE_CATALOG_PATH})",
    )
    parser.add_argument(
        "--init-from-db",
        action="store_true",
        help="Rebuild catalog JSON from ingested documents (merge existing URLs)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show updates without writing to the database",
    )
    args = parser.parse_args()

    try:
        if args.init_from_db:
            return init_catalog_from_db(args.catalog)
        return sync_catalog_to_db(args.catalog, dry_run=args.dry_run)
    except Exception as exc:
        print(f"Failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
