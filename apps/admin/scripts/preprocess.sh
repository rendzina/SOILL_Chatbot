#!/usr/bin/env bash
# SOILL batch OCR wrapper — calls the monorepo CLI from the repository root.
#
# **Created:** 08-06-2026 (UK style).

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

exec uv run soill-ocr-preprocess "$@"
