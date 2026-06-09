#!/usr/bin/env python3
"""
Ingest SourceDocuments into Postgres (pgvector).

Re-run safely: only new or changed files are re-embedded; removed files are dropped.

For image-heavy PDFs, run `uv run soill-ocr-preprocess` first — see
documents/OCR_PDF_PreProcessingWorkflow.md.

Flags:
  --dry-run — preview incremental changes only
  --dry-run-full-reset — preview full reset (read-only counts)
  --full-reset — wipe chunks/documents and local manifest; requires
                 --i-know-this-wipes-data

**Created:** 04-06-2026 (UK style).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from mistralai import Mistral

from soill import config as cfg
from soill import embeddings as emb
from soill import source_extract
from soill import store_pg
from soill.chunking import TextChunk, chunk_text_with_page_labels

_MANIFEST_KEY = "paths"


def _sha256_file(file_path: Path) -> str:
    h = hashlib.sha256()
    with file_path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _load_manifest() -> Dict[str, str]:
    if not cfg.MANIFEST_PATH.is_file():
        return {}
    try:
        with open(cfg.MANIFEST_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return {str(k): str(v) for k, v in (data.get(_MANIFEST_KEY) or {}).items()}
    except (json.JSONDecodeError, OSError):
        return {}


def _save_manifest(paths: Dict[str, str]) -> None:
    cfg.DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        _MANIFEST_KEY: dict(sorted(paths.items())),
        "updated_utc": datetime.now(timezone.utc).isoformat(),
    }
    with open(cfg.MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def _list_source_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in cfg.SUPPORTED_SOURCE_EXTENSIONS:
            files.append(p)
    return sorted(files)


def _rel_key(root: Path, p: Path) -> str:
    return str(p.resolve().relative_to(root.resolve()))


def _remove_local_manifest() -> None:
    try:
        if cfg.MANIFEST_PATH.is_file():
            cfg.MANIFEST_PATH.unlink()
    except OSError as e:
        print(f"Warning: could not remove {cfg.MANIFEST_PATH}: {e}", file=sys.stderr)


def _process_one_file(
    rel_path: str, abs_path: Path, file_hash: str, client: Mistral
) -> int:
    extracted = source_extract.extract_source_words(abs_path)
    cks: list[TextChunk] = chunk_text_with_page_labels(
        extracted.words,
        extracted.locations,
        rel_path,
        file_hash,
    )
    if not cks:
        print(f"  No text extracted, skipping: {rel_path}", file=sys.stderr)
        return 0
    mat = emb.embed_texts(client, [c.text for c in cks], normalise=True)
    now = datetime.now(timezone.utc)
    to_insert: list[dict[str, Any]] = []
    for i, ch in enumerate(cks):
        to_insert.append(
            {
                "chunk_id": ch.chunk_id,
                "source_path": rel_path,
                "source_hash": file_hash,
                "chunk_index": ch.chunk_index,
                "text": ch.text,
                "page_start": ch.page_start,
                "page_end": ch.page_end,
                "source_type": extracted.source_type,
                "location_type": extracted.location_type,
                "location_start": ch.page_start,
                "location_end": ch.page_end,
                "embedding": mat[i].tolist(),
                "created_at": now,
            }
        )
    if to_insert:
        store_pg.insert_chunk_rows(to_insert)
    print(f"  Ingested {len(to_insert)} chunk(s) from: {rel_path}", file=sys.stderr)
    return len(to_insert)


def _dry_run_full_reset(source_files: list[Path]) -> int:
    print("[dry-run full reset] No data will be deleted or ingested.", file=sys.stderr)
    try:
        store_pg.ping_database()
    except Exception as e:
        print(f"Cannot reach database: {e}", file=sys.stderr)
        return 1
    try:
        n_chunks = store_pg.count_chunks()
        n_docs = store_pg.count_document_rows()
    except Exception as e:
        print(f"Failed to read table counts: {e}", file=sys.stderr)
        return 1
    print(
        f"Would delete {n_chunks} chunk row(s) and {n_docs} document row(s).",
        file=sys.stderr,
    )
    print(f"Would remove local manifest if present: {cfg.MANIFEST_PATH}", file=sys.stderr)
    print(
        f"Would re-ingest {len(source_files)} source file(s) under {cfg.SOURCE_DOCUMENTS}.",
        file=sys.stderr,
    )
    for p in source_files:
        print(f"  - {_rel_key(cfg.SOURCE_DOCUMENTS, p)}", file=sys.stderr)
    return 0


def _run_full_reset(source_files: list[Path], current: Dict[str, str]) -> int:
    if not cfg.MISTRAL_API_KEY:
        print("MISTRAL_API_KEY is not set.", file=sys.stderr)
        return 1

    print("Full reset: checking database…", file=sys.stderr)
    try:
        store_pg.ping_database()
    except Exception as e:
        print(f"Cannot reach database: {e}", file=sys.stderr)
        return 1

    try:
        n_chunks, n_docs = store_pg.clear_ingestion_tables()
    except Exception as e:
        print(f"Failed to clear ingestion tables: {e}", file=sys.stderr)
        return 1
    print(
        f"Cleared database: {n_chunks} chunk row(s), {n_docs} document row(s).",
        file=sys.stderr,
    )

    _remove_local_manifest()
    print("Removed local manifest (if it existed).", file=sys.stderr)

    try:
        client = emb.get_client()
    except RuntimeError as e:
        print(f"{e}", file=sys.stderr)
        return 1

    total_chunks = 0
    files_done = 0
    for p in source_files:
        k = _rel_key(cfg.SOURCE_DOCUMENTS, p)
        h = current[k]
        try:
            n = _process_one_file(k, p, h, client)
            total_chunks += n
            store_pg.upsert_document_record(k, h)
            files_done += 1
        except Exception as e:
            print(f"Failed to ingest {k!r}: {type(e).__name__}: {e}", file=sys.stderr)
            print(f"Stopped after {files_done} file(s).", file=sys.stderr)
            return 1

    try:
        _save_manifest({key: current[key] for key in current})
    except OSError as e:
        print(f"Failed to write manifest: {e}", file=sys.stderr)
        return 1

    print(
        f"Full reset complete: {files_done} file(s), {total_chunks} chunk(s) stored.",
        file=sys.stderr,
    )
    return 0


def _run_incremental(dry: bool) -> int:
    if not dry and not cfg.MISTRAL_API_KEY:
        print("MISTRAL_API_KEY is not set (or use --dry-run).", file=sys.stderr)
        return 1

    cfg.SOURCE_DOCUMENTS.mkdir(parents=True, exist_ok=True)
    manifest = _load_manifest()
    source_files = _list_source_files(cfg.SOURCE_DOCUMENTS)
    current: dict[str, str] = {}
    for p in source_files:
        key = _rel_key(cfg.SOURCE_DOCUMENTS, p)
        current[key] = _sha256_file(p)

    to_refresh: list[Path] = [
        p
        for p in source_files
        if current[_rel_key(cfg.SOURCE_DOCUMENTS, p)]
        != manifest.get(_rel_key(cfg.SOURCE_DOCUMENTS, p))
    ]
    removed = set(manifest) - set(current)

    if dry:
        for path in sorted(removed):
            print(f"[dry-run] Would remove chunks for: {path}", file=sys.stderr)
        for p in to_refresh:
            k = _rel_key(cfg.SOURCE_DOCUMENTS, p)
            ch = "changed" if k in manifest else "new"
            print(f"[dry-run] Would ingest ({ch}): {k}", file=sys.stderr)
        if removed or to_refresh:
            print("Dry run only; no changes written.", file=sys.stderr)
        else:
            print("Dry run: nothing to do.", file=sys.stderr)
        return 0

    try:
        store_pg.ping_database()
    except Exception as e:
        print(f"Cannot reach database: {e}", file=sys.stderr)
        return 1

    for path in sorted(removed):
        n = store_pg.delete_chunks_for_path(path)
        store_pg.remove_document_record(path)
        print(f"Removed {n} chunk(s) for missing file: {path}", file=sys.stderr)

    client: Optional[Mistral] = None
    if to_refresh:
        client = emb.get_client()

    if to_refresh and client is not None:
        for p in to_refresh:
            k = _rel_key(cfg.SOURCE_DOCUMENTS, p)
            h = current[k]
            if k in manifest:
                store_pg.delete_chunks_for_path(k)
            try:
                _process_one_file(k, p, h, client)
            except Exception as e:
                print(f"Failed to ingest {k!r}: {e}", file=sys.stderr)
                return 1
            store_pg.upsert_document_record(k, h)

    _save_manifest({k: current[k] for k in current})

    if to_refresh or removed:
        print(
            f"Ingestion complete ({len(to_refresh)} updated, {len(removed)} removed).",
            file=sys.stderr,
        )
    else:
        print("No new, changed, or removed source files. Manifest is up to date.", file=sys.stderr)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ingest SourceDocuments into Postgres (pgvector).",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--dry-run-full-reset", action="store_true")
    parser.add_argument("--full-reset", action="store_true")
    parser.add_argument("--i-know-this-wipes-data", action="store_true")
    args = parser.parse_args()

    mode_count = sum([args.dry_run, args.dry_run_full_reset, args.full_reset])
    if mode_count > 1:
        print("Use only one of: --dry-run, --dry-run-full-reset, --full-reset.", file=sys.stderr)
        return 1

    cfg.SOURCE_DOCUMENTS.mkdir(parents=True, exist_ok=True)
    source_files = _list_source_files(cfg.SOURCE_DOCUMENTS)
    current = {
        _rel_key(cfg.SOURCE_DOCUMENTS, p): _sha256_file(p) for p in source_files
    }

    if args.dry_run_full_reset:
        return _dry_run_full_reset(source_files)

    if args.full_reset:
        if not args.i_know_this_wipes_data:
            print(
                "Refusing --full-reset without --i-know-this-wipes-data.",
                file=sys.stderr,
            )
            return 1
        return _run_full_reset(source_files, current)

    return _run_incremental(dry=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
