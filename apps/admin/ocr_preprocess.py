#!/usr/bin/env python3
"""
Batch OCR for image-heavy PDFs (ocrmypdf wrapper).

Place raw scans in PDFPreProcessing/IncomingScans/, then promote approved
outputs from OCR_Output/ into SourceDocuments/ before running soill-process.

Flags:
  --dry-run — list jobs without running ocrmypdf
  --force-ocr — OCR every page (default: --skip-text, pages with text unchanged)

**Created:** 08-06-2026 (UK style).
"""

from __future__ import annotations

import argparse
import sys

from soill import ocr_preprocess


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run batch OCR on PDFs in PDFPreProcessing/IncomingScans/ using ocrmypdf."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview OCR jobs without running ocrmypdf.",
    )
    parser.add_argument(
        "--force-ocr",
        action="store_true",
        help="OCR all pages, even when text is already present.",
    )
    parser.add_argument(
        "--skip-text",
        action="store_true",
        help="Only OCR pages without extractable text (overrides OCR_FORCE env).",
    )
    parser.add_argument(
        "--language",
        default=None,
        help="ocrmypdf language code (default: OCR_LANGUAGE env or eng).",
    )
    args = parser.parse_args()

    if args.force_ocr and args.skip_text:
        print("Use only one of: --force-ocr, --skip-text.", file=sys.stderr)
        return 1

    force: bool | None
    if args.force_ocr:
        force = True
    elif args.skip_text:
        force = False
    else:
        force = None

    _, exit_code = ocr_preprocess.run_batch(
        force_ocr=force,
        language=args.language,
        dry_run=args.dry_run,
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
