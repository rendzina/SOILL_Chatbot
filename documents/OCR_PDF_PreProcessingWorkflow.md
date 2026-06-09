# OCR PDF pre-processing workflow (batch)

Some PDFs are image-heavy and contain little or no direct extractable text, but they have text in images on the page. In that case, run OCR **before** ingestion so `soill-process` can chunk meaningful text. By default, if a given page already has extractable text, it is **not** re-OCR'd (`--skip-text`). Use `--force-ocr` when every page must be processed.

**Created:** 9-06-2026 (UK style).  
**Credits:** Professor Stephen Hallett, Cranfield University, 2026.

---

## Prerequisites

- Python **3.11–3.13** and [uv](https://docs.astral.sh/uv/) — see the [main README](../README.md).
- **`ocrmypdf`** on your PATH (system install, not a Python package in this repo):
  - macOS: `brew install ocrmypdf`
  - Debian/Ubuntu: `apt install ocrmypdf`
- After promotion to `SourceDocuments/`, a Postgres database with pgvector — run `uv run soill-db-init` once, then ingest with `uv run soill-process`.

---

## Scope

This workflow uses folders under `PDFPreProcessing/` at the repository root:

| Path | Role |
|------|------|
| `PDFPreProcessing/IncomingScans/` | Raw PDF queue (input only) |
| `PDFPreProcessing/OCR_Output/` | OCR-generated searchable PDFs (`<name>.ocr.pdf`) |
| `PDFPreProcessing/OCR_Failed/` | Files that failed OCR and need manual review |
| `PDFPreProcessing/OCR_Processing/Logs/` | Per-file logs plus `batch-summary.log` |
| `SourceDocuments/` | Approved files for indexing by `soill-process` |

Only approved OCR outputs should be copied to `SourceDocuments/` for indexing. OCR folders and logs are gitignored (except `.gitkeep` placeholders).

Optional override: set `PDF_PREPROCESSING_ROOT` in `.env` to use a different base directory.

---

## Principles

- Keep originals separate from OCR outputs.
- Never index partial or failed OCR results.
- Use deterministic file naming (`<name>.ocr.pdf`).
- Keep per-file logs and a batch summary log.

---

## Running the batch

From the repository root:

```bash
uv run soill-ocr-preprocess
```

Or use the shell wrapper (same behaviour):

```bash
bash apps/admin/scripts/preprocess.sh
```

### Useful flags

| Flag | Purpose |
|------|---------|
| `--dry-run` | List jobs without running ocrmypdf |
| `--skip-text` | Only OCR pages without extractable text (**default** when `OCR_FORCE` is not set) |
| `--force-ocr` | OCR every page, even when text is already present |
| `--language eng` | ocrmypdf language code (default: `OCR_LANGUAGE` env or `eng`) |

Environment variables (see [`.env.example`](../.env.example)):

- `OCR_LANGUAGE` — default language for ocrmypdf
- `OCR_FORCE=true` — same as always passing `--force-ocr`
- `PDF_PREPROCESSING_ROOT` — optional path override for the pipeline folders

---

## Expected outputs

For each `IncomingScans/<name>.pdf`, expect:

- `OCR_Output/<name>.ocr.pdf`
- `OCR_Processing/Logs/<name>.log`
- A line in `OCR_Processing/Logs/batch-summary.log`:
  - `OK: ...` on success
  - `FAIL: ...` on failure (source moved to `OCR_Failed/`)

---

## Quality gate before indexing

Before copying files to `SourceDocuments/`, check:

1. Output PDF exists and is non-empty.
2. Log has no hard OCR errors.
3. PDF allows text selection or search on expected pages.

If quality is poor, re-run that file with adjusted options (`--language`, `--force-ocr`, or ocrmypdf flags such as `--deskew` — extend the CLI if needed).

---

## Promotion to `SourceDocuments/`

When approved, copy OCR outputs into `SourceDocuments/` (keep or flatten paths as you prefer), then from the repository root:

```bash
uv run soill-process --dry-run
uv run soill-process
```

Start the chat UI or API only after ingestion succeeds — see the [main README](../README.md).

---

## How this interacts with SOILL ingestion

- `soill-process` hashes each file and only reprocesses changed or new files.
- If an OCR update changes the PDF bytes, old chunks for that source path are removed and the file is re-chunked.
- Unchanged files are skipped.
- Ingestion uses PyMuPDF text extraction only — it does **not** run OCR itself. Scanned PDFs must go through this workflow first.

---

## Implementation

| Component | Location |
|-----------|----------|
| OCR batch logic | [`packages/soill/src/soill/ocr_preprocess.py`](../packages/soill/src/soill/ocr_preprocess.py) |
| CLI | [`apps/admin/ocr_preprocess.py`](../apps/admin/ocr_preprocess.py) (`soill-ocr-preprocess`) |
| Shell wrapper | [`apps/admin/scripts/preprocess.sh`](../apps/admin/scripts/preprocess.sh) |
| Paths and defaults | [`packages/soill/src/soill/config.py`](../packages/soill/src/soill/config.py) |

---

## Operational notes

- Keep private scan folders outside version control where appropriate (contents are gitignored by default).
- Archive processed originals if retention policy requires it.
- Rotate logs periodically for long-running operations.

---

## Related documents

- [README](../README.md) — quick start, admin commands, environment variables
- [approach.md](approach.md) — architectural rationale
- [deployment.md](deployment.md) — FastAPI deployment and website integration
