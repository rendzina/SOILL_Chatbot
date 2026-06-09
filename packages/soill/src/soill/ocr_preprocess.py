"""
Batch OCR for image-heavy PDFs using ocrmypdf.

Searchable PDFs are written to OCR_Output/ for promotion to SourceDocuments/
before running soill-process.

**Created:** 08-06-2026 (UK style).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

from . import config as cfg


@dataclass(frozen=True)
class OCRJob:
    """One PDF queued for OCR."""

    source: Path
    output: Path
    log_path: Path


@dataclass
class OCRResult:
    """Outcome of one OCR job."""

    job: OCRJob
    ok: bool
    message: str


def ocrmypdf_available() -> bool:
    return shutil.which("ocrmypdf") is not None


def ensure_ocr_directories() -> None:
    """Create OCR pipeline folders if missing."""
    for directory in (
        cfg.OCR_INCOMING_DIR,
        cfg.OCR_OUTPUT_DIR,
        cfg.OCR_FAILED_DIR,
        cfg.OCR_LOGS_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)


def list_incoming_pdfs(incoming_dir: Optional[Path] = None) -> list[Path]:
    root = incoming_dir or cfg.OCR_INCOMING_DIR
    if not root.is_dir():
        return []
    return sorted(
        p for p in root.iterdir() if p.is_file() and p.suffix.lower() == ".pdf"
    )


def build_jobs(
    sources: Iterable[Path],
    *,
    output_dir: Optional[Path] = None,
    logs_dir: Optional[Path] = None,
) -> list[OCRJob]:
    out_root = output_dir or cfg.OCR_OUTPUT_DIR
    log_root = logs_dir or cfg.OCR_LOGS_DIR
    jobs: list[OCRJob] = []
    for source in sources:
        base = source.stem
        jobs.append(
            OCRJob(
                source=source,
                output=out_root / f"{base}.ocr.pdf",
                log_path=log_root / f"{base}.log",
            )
        )
    return jobs


def _append_batch_summary(line: str, summary_path: Optional[Path] = None) -> None:
    path = summary_path or cfg.OCR_BATCH_SUMMARY_LOG
    path.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"{stamp} {line}\n")


def _ocr_command(job: OCRJob, *, force_ocr: bool, language: str) -> list[str]:
    cmd = ["ocrmypdf", "--language", language]
    if force_ocr:
        cmd.append("--force-ocr")
    else:
        cmd.append("--skip-text")
    cmd.extend([str(job.source), str(job.output)])
    return cmd


def run_job(
    job: OCRJob,
    *,
    force_ocr: bool = False,
    language: Optional[str] = None,
    dry_run: bool = False,
    failed_dir: Optional[Path] = None,
    summary_path: Optional[Path] = None,
) -> OCRResult:
    lang = (language or cfg.OCR_LANGUAGE).strip() or "eng"
    mode = "force-ocr" if force_ocr else "skip-text"

    if dry_run:
        return OCRResult(
            job=job,
            ok=True,
            message=(
                f"[dry-run] Would run ocrmypdf --{mode} --language {lang}: "
                f"{job.source.name} -> {job.output.name}"
            ),
        )

    job.log_path.parent.mkdir(parents=True, exist_ok=True)
    job.output.parent.mkdir(parents=True, exist_ok=True)
    cmd = _ocr_command(job, force_ocr=force_ocr, language=lang)

    with job.log_path.open("w", encoding="utf-8") as log_handle:
        log_handle.write(f"Command: {' '.join(cmd)}\n\n")
        log_handle.flush()
        completed = subprocess.run(
            cmd,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )

    if completed.returncode == 0 and job.output.is_file() and job.output.stat().st_size > 0:
        line = f"OK: {job.source} -> {job.output}"
        _append_batch_summary(line, summary_path)
        return OCRResult(job=job, ok=True, message=line)

    fail_root = failed_dir or cfg.OCR_FAILED_DIR
    fail_root.mkdir(parents=True, exist_ok=True)
    try:
        shutil.move(str(job.source), str(fail_root / job.source.name))
        moved = f" (moved to {fail_root / job.source.name})"
    except OSError as exc:
        moved = f" (could not move source: {exc})"

    line = f"FAIL: {job.source}{moved}"
    _append_batch_summary(line, summary_path)
    return OCRResult(job=job, ok=False, message=line)


def run_batch(
    *,
    force_ocr: Optional[bool] = None,
    language: Optional[str] = None,
    dry_run: bool = False,
    incoming_dir: Optional[Path] = None,
) -> tuple[list[OCRResult], int]:
    """
    Process all PDFs in IncomingScans/.

    Returns (results, exit_code). Exit code 0 if all succeeded or dry-run;
    1 if ocrmypdf is missing or any job failed.
    """
    if not dry_run and not ocrmypdf_available():
        print(
            "ocrmypdf is not on your PATH. Install it before running OCR "
            "(e.g. brew install ocrmypdf on macOS, apt install ocrmypdf on Debian).",
            file=sys.stderr,
        )
        return [], 1

    ensure_ocr_directories()
    sources = list_incoming_pdfs(incoming_dir)
    if not sources:
        print(
            f"No PDF files in {incoming_dir or cfg.OCR_INCOMING_DIR}.",
            file=sys.stderr,
        )
        return [], 0

    use_force = cfg.OCR_FORCE if force_ocr is None else force_ocr
    jobs = build_jobs(sources)
    results: list[OCRResult] = []
    failures = 0

    for job in jobs:
        result = run_job(
            job,
            force_ocr=use_force,
            language=language,
            dry_run=dry_run,
        )
        print(result.message, file=sys.stderr)
        results.append(result)
        if not result.ok:
            failures += 1

    if dry_run:
        print("Dry run only; no OCR output written.", file=sys.stderr)
        return results, 0

    if failures:
        print(f"OCR batch finished with {failures} failure(s).", file=sys.stderr)
        return results, 1

    print(f"OCR batch complete: {len(results)} file(s) processed.", file=sys.stderr)
    return results, 0
