#!/usr/bin/env python3
"""
Reporter.py

Export PostgreSQL ``soill_conversations`` rows to a compact, paginated PDF under
``Reports/``. Uses ``DATABASE_URL`` from ``.env`` (same database as the Chainlit
logging pipeline). Each logged turn includes ``thread_id`` when the Chainlit app
recorded it (useful for grouping multi-turn exchanges in external analysis).

The conversations-over-time figure chooses **daily**, **ISO weekly**, or
**calendar monthly** bars from the inclusive selection span (explicit
``--from-date`` / ``--to-date``, or the span of returned rows when an end is open).
Thresholds: 90 and 548 calendar days. If **both** date flags are set, span is the
requested window only (not data density within it); see README.

**Created:** 15-05-2026 (UK style).  
**Updated:** 20-05-2026 — documents multi-turn ``thread_id`` in logged rows.  
**Credits:** Professor Stephen Hallett, Cranfield University, 2026.
"""

from __future__ import annotations

import argparse
import io
import logging
import re
import sys
from collections import defaultdict
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

import fitz  # PyMuPDF

from soill import config as cfg
from soill import store_pg

logger = logging.getLogger(__name__)

_ROOT = cfg.repo_root()
REPORTS_DIR = cfg.REPORTS_DIR
LOGO_PATH = _ROOT / "apps" / "chatbot" / "public" / "logo_light.png"

_FONT = "helv"
_FONT_BOLD = "hebo"
_BODY_SIZE = 8
_META_SIZE = 7
_SUBTITLE_SIZE = 9
_TITLE_SIZE = 13
_PAGE_W, _PAGE_H = 595, 842
_MARGIN_X = 42
_MARGIN_TOP = 40
_MARGIN_BOTTOM = 52
_CONTENT_BOTTOM = _PAGE_H - _MARGIN_BOTTOM - 22

# Inclusive selection span (calendar days) chooses chart granularity.
_SPAN_USE_DAILY_BARS_MAX = 90
_SPAN_USE_WEEKLY_BARS_MAX = 548  # ~18 months; longer spans use monthly buckets


def _iso_date(s: str) -> date:
    return datetime.strptime(s.strip(), "%Y-%m-%d").date()


def _utc_bounds(
    d_from: Optional[date], d_to: Optional[date]
) -> dict[str, Any]:
    flt: dict[str, Any] = {}
    bounds: dict[str, Any] = {}
    if d_from is not None:
        start = datetime.combine(d_from, time.min, tzinfo=timezone.utc)
        bounds["$gte"] = start
    if d_to is not None:
        end = datetime.combine(d_to, time(23, 59, 59, 999999), tzinfo=timezone.utc)
        bounds["$lte"] = end
    if bounds:
        flt["created_at"] = bounds
    return flt


def _ensure_utc(dt: Any) -> datetime:
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    return datetime.now(timezone.utc)


def _fmt_ts(dt: Any) -> str:
    d = _ensure_utc(dt)
    return d.strftime("%d-%m-%Y %H:%M UTC")


def _fmt_uk_date(d: Optional[date]) -> str:
    if d is None:
        return "—"
    return d.strftime("%d-%m-%Y")


def _word_wrap_line(
    line: str, font: fitz.Font, fontsize: float, max_width: float
) -> Iterator[str]:
    line = line.replace("\r\n", "\n").replace("\r", "\n")
    for paragraph in line.split("\n"):
        if not paragraph.strip():
            yield ""
            continue
        words = paragraph.split()
        current: list[str] = []
        for w in words:
            trial = (" ".join(current + [w])).strip()
            tw = font.text_length(trial, fontsize)
            if current and tw > max_width:
                yield " ".join(current)
                current = [w]
            else:
                current.append(w)
        if current:
            yield " ".join(current)


def _expand_entry_lines(meta: dict[str, Any]) -> list[tuple[str, bool]]:
    """Each line is (text, bold). Question label and body are bold for readability."""
    lines: list[tuple[str, bool]] = []
    ts = _fmt_ts(meta.get("created_at"))
    parts = [f"{ts}"]
    if meta.get("client_ip"):
        parts.append(f"IP {meta['client_ip']}")
    if meta.get("forwarded_for"):
        parts.append(f"X-Forwarded-For {meta['forwarded_for']}")
    if meta.get("session_id"):
        sid = meta["session_id"]
        if isinstance(sid, str) and len(sid) > 12:
            parts.append(f"session {sid[:12]}…")
        else:
            parts.append(f"session {sid}")
    lines.append((" · ".join(parts), False))
    lines.append(
        (
            f"Cited sources: {meta.get('cited_sources_count', 0)} | "
            f"models chat/embed: {meta.get('chat_model', '')} / "
            f"{meta.get('embed_model', '')}",
            False,
        )
    )
    lines.append(("", False))
    lines.append(("Q:", True))
    q = (meta.get("question") or "").strip() or "(empty)"
    lines.append((q, True))
    lines.append(("", False))
    err = meta.get("error")
    if err:
        lines.append(("Error:", False))
        lines.append((str(err), False))
        lines.append(("", False))
    ans = meta.get("answer")
    if ans is not None and str(ans).strip():
        lines.append(("A:", False))
        lines.append((str(ans).strip(), False))
    lines.append(("", False))
    return lines


def _compute_statistics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    sessions: set[str] = set()
    ips: set[str] = set()
    threads: set[str] = set()
    by_day: dict[date, int] = defaultdict(int)
    for r in rows:
        dt = r.get("created_at")
        if dt is not None:
            by_day[_ensure_utc(dt).date()] += 1
        sid = r.get("session_id")
        if sid:
            sessions.add(str(sid))
        if r.get("client_ip"):
            ips.add(str(r["client_ip"]))
        tid = r.get("thread_id")
        if tid:
            threads.add(str(tid))
    sorted_days = sorted(by_day.items())
    return {
        "n": len(rows),
        "unique_sessions": len(sessions),
        "unique_ips": len(ips),
        "unique_threads": len(threads),
        "by_day": sorted_days,
        "first_date": sorted_days[0][0] if sorted_days else None,
        "last_date": sorted_days[-1][0] if sorted_days else None,
    }


def _filter_caption(
    d_from: Optional[date], d_to: Optional[date]
) -> list[str]:
    if d_from is None and d_to is None:
        return ["Selection: all records in the database (UTC timestamps)."]
    a = _fmt_uk_date(d_from) if d_from else "open start"
    b = _fmt_uk_date(d_to) if d_to else "open end"
    return [
        f"Selection: inclusive UTC date filter from {a} to {b} on `created_at`."
    ]


def _questions_wordcloud_png(rows: list[dict[str, Any]]) -> Optional[bytes]:
    """
    Build a PNG (bytes) word cloud from all `question` fields, or None if skipped.
    """
    try:
        from wordcloud import STOPWORDS, WordCloud
    except ImportError:
        logger.warning("wordcloud not installed; run: pip install wordcloud")
        return None
    parts: list[str] = []
    for r in rows:
        q = (r.get("question") or "").strip()
        if q:
            parts.append(q)
    text = " ".join(parts)
    if len(text) < 48:
        return None
    extra = {
        "http",
        "https",
        "www",
        "com",
        "org",
        "soill",
        "chatbot",
        "pdf",
    }
    stop = STOPWORDS | extra
    try:
        wc = WordCloud(
            width=1100,
            height=480,
            background_color="white",
            max_words=70,
            colormap="viridis",
            stopwords=stop,
            min_font_size=8,
            relative_scaling=0.5,
            collocations=True,
        ).generate(text)
        buf = io.BytesIO()
        wc.to_image().save(buf, format="PNG")
        return buf.getvalue()
    except (ValueError, RuntimeError) as e:
        logger.warning("Word cloud generation failed: %s", e)
        return None


def _selection_span_days(
    date_from: Optional[date],
    date_to: Optional[date],
    stats: dict[str, Any],
) -> int:
    """
    Inclusive calendar span used to choose daily vs weekly vs monthly buckets.
    Uses explicit ``--from-date`` / ``--to-date`` when both are set; otherwise
    the overlap of filters with data, or data extent when unbounded.
    """
    fd = stats.get("first_date")
    ld = stats.get("last_date")

    if date_from is not None and date_to is not None:
        return max(1, (date_to - date_from).days + 1)

    if date_from is not None:
        if ld is not None:
            return max(1, (ld - date_from).days + 1)
        return 1

    if date_to is not None:
        if fd is not None:
            return max(1, (date_to - fd).days + 1)
        return 1

    if fd is not None and ld is not None:
        return max(1, (ld - fd).days + 1)

    return 1


def _aggregate_counts_by_iso_week(
    by_day: list[tuple[date, int]],
) -> list[tuple[tuple[int, int], int]]:
    """Return sorted ((ISO year, ISO week), count) for UTC calendar dates."""
    week_map: dict[tuple[int, int], int] = defaultdict(int)
    for d, c in by_day:
        y, w, _ = d.isocalendar()
        week_map[(y, w)] += c
    return sorted((k, week_map[k]) for k in sorted(week_map))


def _aggregate_counts_by_month(
    by_day: list[tuple[date, int]],
) -> list[tuple[tuple[int, int], int]]:
    """Return sorted ((year, month), count)."""
    month_map: dict[tuple[int, int], int] = defaultdict(int)
    for d, c in by_day:
        month_map[(d.year, d.month)] += c
    return sorted((k, month_map[k]) for k in sorted(month_map))


def _build_time_series_chart(
    date_from: Optional[date],
    date_to: Optional[date],
    stats: dict[str, Any],
) -> tuple[str, list[tuple[str, int]], str]:
    """
    Title, (x-axis label, count) bars, and footnote for the activity chart.
    Granularity follows selection span: daily, ISO week, or calendar month.
    """
    by_day: list[tuple[date, int]] = stats["by_day"]
    if not by_day:
        return (
            "Conversations per calendar day (UTC)",
            [],
            "No dated rows in this selection.",
        )

    span = _selection_span_days(date_from, date_to, stats)

    if span <= _SPAN_USE_DAILY_BARS_MAX:
        bars = [(d.strftime("%d/%m"), c) for d, c in by_day]
        peak_d, peak_v = max(by_day, key=lambda t: t[1])
        foot = f"Largest daily count: {peak_v} on {_fmt_uk_date(peak_d)} (UTC)."
        return ("Conversations per calendar day (UTC)", bars, foot)

    if span <= _SPAN_USE_WEEKLY_BARS_MAX:
        keyed = _aggregate_counts_by_iso_week(by_day)
        bars = [
            (f"{str(y)[2:]}-W{w:02d}", c) for (y, w), c in keyed
        ]
        peak_idx = max(range(len(keyed)), key=lambda i: keyed[i][1])
        (py, pw), peak_v = keyed[peak_idx]
        foot = (
            f"Largest weekly total: {peak_v} in ISO week {pw:02d} {py} "
            "(UTC dates aggregated by day)."
        )
        return (
            "Conversations per ISO week (UTC calendar dates aggregated by day)",
            bars,
            foot,
        )

    keyed_m = _aggregate_counts_by_month(by_day)
    bars = []
    for (y, m), c in keyed_m:
        label = date(y, m, 1).strftime("%m/%Y")
        bars.append((label, c))
    peak_idx = max(range(len(keyed_m)), key=lambda i: keyed_m[i][1])
    (py, pm), peak_v = keyed_m[peak_idx]
    peak_label = date(py, pm, 1).strftime("%m/%Y")
    foot = f"Largest monthly total: {peak_v} in {peak_label} (UTC)."
    return (
        "Conversations per calendar month (UTC)",
        bars,
        foot,
    )


def _summary_paragraph(stats: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    if not rows:
        return (
            "There are no conversations in this selection. "
            "Adjust the date range or ensure chat logging is enabled, then run this reporter again."
        )
    n = stats["n"]
    fs, fi, ft = (
        stats["unique_sessions"],
        stats["unique_ips"],
        stats["unique_threads"],
    )
    fd = _fmt_uk_date(stats["first_date"])
    ld = _fmt_uk_date(stats["last_date"])
    return (
        f"This export contains {n} conversation record(s). "
        f"Approximately {fs} distinct Chainlit session(s) contributed rows; "
        f"{fi} distinct client IP address(es) and {ft} distinct thread id(s) were observed "
        f"where those fields were recorded. "
        f"Conversation timestamps in this set span {fd} to {ld} (UTC calendar dates)."
    )


def _logo_metrics() -> Optional[tuple[float, float]]:
    """Return (display width, height) for the header logo, or None."""
    if not LOGO_PATH.is_file():
        return None
    try:
        pix = fitz.Pixmap(str(LOGO_PATH))
        ar = pix.width / max(pix.height, 1)
        h = 40.0
        return (h * ar, h)
    except Exception:
        return None


def _draw_time_series_bar_chart(
    page: fitz.Page,
    y_top: float,
    title: str,
    bars: list[tuple[str, int]],
    foot: str,
    font: fitz.Font,
) -> float:
    """Draw a bar chart of pre-bucketed counts (labels already shortened if needed)."""
    label_gap = 20
    chart_h = 92
    page.insert_text(
        (_MARGIN_X, y_top + 10),
        title,
        fontname=_FONT,
        fontsize=_SUBTITLE_SIZE,
        color=(0, 0, 0),
    )
    y0 = y_top + 22
    if not bars:
        page.insert_text(
            (_MARGIN_X, y0 + 28),
            foot,
            fontname=_FONT,
            fontsize=_BODY_SIZE,
            color=(0.3, 0.3, 0.3),
        )
        return y0 + chart_h + label_gap + 6

    max_c = max(c for _, c in bars) or 1
    n = len(bars)
    chart_w = _PAGE_W - 2 * _MARGIN_X
    gap = max(0.8, min(3.5, chart_w / max(n * 2.5, 1)))
    bar_w = max((chart_w - gap * (n + 1)) / n, 1.2)
    y_axis = y0 + chart_h
    x_start = _MARGIN_X + gap
    label_fs = _META_SIZE - (1 if n > 48 else 0)

    for i, (label, cnt) in enumerate(bars):
        bar_h = chart_h * (cnt / max_c)
        x = x_start + i * (bar_w + gap)
        y1 = y_axis - bar_h
        shade = 0.5 + 0.18 * (i % 2)
        page.draw_rect(
            fitz.Rect(x, y1, x + bar_w, y_axis),
            color=(0.42, 0.42, 0.48),
            fill=(shade, 0.56, 0.74),
            width=0.2,
        )
        step = max(1, n // 14) if n > 14 else 1
        if i % step != 0 and i != n - 1:
            continue
        tw = font.text_length(label, label_fs)
        lx = x + (bar_w - tw) / 2
        page.insert_text(
            (lx, y_axis + 9),
            label,
            fontname=_FONT,
            fontsize=label_fs,
            color=(0.22, 0.22, 0.22),
        )

    page.draw_line(
        (x_start - gap, y_axis),
        (x_start - gap + n * (bar_w + gap), y_axis),
        width=0.55,
        color=(0.32, 0.32, 0.32),
    )
    page.insert_text(
        (_MARGIN_X, y_axis + label_gap),
        foot,
        fontname=_FONT,
        fontsize=_META_SIZE,
        color=(0.28, 0.28, 0.28),
    )
    return y_axis + label_gap + 14


class _PdfWriter:
    def __init__(self) -> None:
        self.doc = fitz.open()
        self.font = fitz.Font(_FONT)
        self.font_bold = fitz.Font(_FONT_BOLD)
        self.max_text_w = _PAGE_W - 2 * _MARGIN_X
        self.page: Optional[fitz.Page] = None
        self._y: float = _MARGIN_TOP

    def _new_page(self) -> None:
        self.page = self.doc.new_page(width=_PAGE_W, height=_PAGE_H)
        self._y = _MARGIN_TOP

    def _ensure(self, dy: float) -> None:
        if self.page is None:
            self._new_page()
        elif self._y + dy > _CONTENT_BOTTOM:
            self._new_page()

    def text_lines(
        self,
        lines: list[str] | list[tuple[str, bool]],
        size: float = _BODY_SIZE,
    ) -> None:
        lh = size * 1.38
        for item in lines:
            if isinstance(item, tuple):
                raw, use_bold = item
            else:
                raw, use_bold = item, False
            face = self.font_bold if use_bold else self.font
            fname = _FONT_BOLD if use_bold else _FONT
            for wl in _word_wrap_line(raw, face, size, self.max_text_w):
                self._ensure(lh)
                p = self.page
                assert p is not None
                p.insert_text(
                    (_MARGIN_X, self._y),
                    wl,
                    fontname=fname,
                    fontsize=size,
                    color=(0, 0, 0),
                )
                self._y += lh

    def separator(self) -> None:
        self._ensure(6)
        p = self.page
        assert p is not None
        y = self._y + 2
        p.draw_line(
            (_MARGIN_X, y),
            (_PAGE_W - _MARGIN_X, y),
            width=0.4,
            color=(0.35, 0.35, 0.35),
        )
        self._y = y + 14

    def rule_before_transcript(self) -> None:
        self._ensure(10)
        p = self.page
        assert p is not None
        y = self._y + 4
        p.draw_line(
            (_MARGIN_X, y),
            (_PAGE_W - _MARGIN_X, y),
            width=1.0,
            color=(0.18, 0.18, 0.18),
        )
        self._y = y + 20

    def add_report_header(
        self,
        *,
        filter_lines: list[str],
        stats: dict[str, Any],
        rows: list[dict[str, Any]],
        date_from: Optional[date],
        date_to: Optional[date],
        generated_utc: datetime,
    ) -> None:
        self._new_page()
        page = self.page
        assert page is not None

        title_x = _MARGIN_X
        lm = _logo_metrics()
        if lm:
            lw, lh = lm
            rect = fitz.Rect(_MARGIN_X, _MARGIN_TOP, _MARGIN_X + lw, _MARGIN_TOP + lh)
            try:
                page.insert_image(rect, filename=str(LOGO_PATH))
            except Exception:
                lh = 0.0
            title_x = rect.x1 + 12
        else:
            lh = 0.0

        page.insert_text(
            (title_x, _MARGIN_TOP + 26),
            "SOILL Public RAG Chatbot — Conversation Reporter",
            fontname=_FONT,
            fontsize=_TITLE_SIZE,
            color=(0.08, 0.08, 0.08),
        )
        gen_s = generated_utc.strftime("%d-%m-%Y %H:%M UTC")
        page.insert_text(
            (title_x, _MARGIN_TOP + 44),
            f"Generated: {gen_s}",
            fontname=_FONT,
            fontsize=_META_SIZE,
            color=(0.38, 0.38, 0.38),
        )

        self._y = _MARGIN_TOP + max(lh, 52) + 14
        for fl in filter_lines:
            self.text_lines([fl], size=_SUBTITLE_SIZE)

        db_mask = re.sub(r"//[^/@\s]+@", "//***@", cfg.MONGODB_URI)
        self.text_lines([f"Database URI (sanitised): {db_mask}"], size=_META_SIZE)
        self._y += 2
        self.text_lines([_summary_paragraph(stats, rows)], size=_BODY_SIZE)
        self._y += 4

        wc_png = _questions_wordcloud_png(rows)
        wc_h = 128.0
        title_band = _SUBTITLE_SIZE * 1.38 + 6
        wc_block = title_band + wc_h + 14
        if self._y + wc_block > _CONTENT_BOTTOM:
            self._new_page()

        page = self.page
        assert page is not None
        self.text_lines(
            ["Question themes — word cloud (all user questions in this report)", ""],
            size=_SUBTITLE_SIZE,
        )
        if wc_png:
            ir = fitz.Rect(
                _MARGIN_X,
                self._y,
                _PAGE_W - _MARGIN_X,
                self._y + wc_h,
            )
            try:
                page.insert_image(ir, stream=wc_png)
                self._y += wc_h + 10
            except Exception as e:
                logger.warning("Could not embed word cloud: %s", e)
                self.text_lines(
                    ["(Word cloud could not be embedded.)"],
                    size=_META_SIZE,
                )
                self._y += 6
        else:
            self.text_lines(
                [
                    "(Word cloud omitted: not enough question text in this selection, "
                    "or `wordcloud` failed to build — see logs.)"
                ],
                size=_META_SIZE,
            )
            self._y += 8

        chart_h_est = 160.0
        if self._y + chart_h_est > _CONTENT_BOTTOM:
            self._new_page()

        page = self.page
        assert page is not None
        ch_title, ch_bars, ch_foot = _build_time_series_chart(
            date_from, date_to, stats
        )
        cb = _draw_time_series_bar_chart(
            page, self._y, ch_title, ch_bars, ch_foot, self.font
        )
        self._y = cb

    def add_footer_page_numbers(self) -> None:
        n = self.doc.page_count
        for i in range(n):
            pg = self.doc.load_page(i)
            label = f"Page {i + 1} of {n}"
            tw = self.font.text_length(label, _META_SIZE)
            x = (_PAGE_W - tw) / 2
            pg.insert_text(
                (x, _PAGE_H - 28),
                label,
                fontname=_FONT,
                fontsize=_META_SIZE,
                color=(0.25, 0.25, 0.25),
            )

    def save(self, path: Path) -> None:
        self.doc.save(path.as_posix())
        self.doc.close()


def fetch_conversations(
    date_from: Optional[date], date_to: Optional[date]
) -> list[dict[str, Any]]:
    store_pg.ping_database()
    flt = _utc_bounds(date_from, date_to)
    return store_pg.fetch_conversations(
        flt.get("created_at", {}).get("$gte"),
        flt.get("created_at", {}).get("$lte"),
    )


def build_pdf(
    out_path: Path,
    rows: list[dict[str, Any]],
    date_from: Optional[date],
    date_to: Optional[date],
) -> None:
    stats = _compute_statistics(rows)
    writer = _PdfWriter()
    writer.add_report_header(
        filter_lines=_filter_caption(date_from, date_to),
        stats=stats,
        rows=rows,
        date_from=date_from,
        date_to=date_to,
        generated_utc=datetime.now(timezone.utc),
    )
    writer.text_lines(["Conversation transcript", ""], size=_SUBTITLE_SIZE)
    writer.rule_before_transcript()

    if not rows:
        writer.text_lines(["No records matched the filter.", ""])
    else:
        for i, row in enumerate(rows):
            if i > 0:
                writer.separator()
            writer.text_lines(_expand_entry_lines(row))

    writer.add_footer_page_numbers()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    writer.save(out_path)


def default_output_path(d_from: Optional[date], d_to: Optional[date]) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    if d_from is None and d_to is None:
        name = f"SOILL_conversations_all_{stamp}.pdf"
    else:
        a = d_from.isoformat() if d_from else "start"
        b = d_to.isoformat() if d_to else "end"
        name = f"SOILL_conversations_{a}_to_{b}_{stamp}.pdf"
    return REPORTS_DIR / name


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(
        description="Generate a PDF report from soill_conversations (Postgres).",
    )
    p.add_argument(
        "--from-date",
        dest="date_from",
        metavar="YYYY-MM-DD",
        type=_iso_date,
        help="Inclusive UTC start date (default: no lower bound)",
    )
    p.add_argument(
        "--to-date",
        dest="date_to",
        metavar="YYYY-MM-DD",
        type=_iso_date,
        help="Inclusive UTC end date (default: no upper bound)",
    )
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output PDF path (default under Reports/ with a timestamp)",
    )
    args = p.parse_args(argv)

    if args.date_from and args.date_to and args.date_from > args.date_to:
        print("Error: --from-date must not be after --to-date.", file=sys.stderr)
        return 2

    try:
        rows = fetch_conversations(args.date_from, args.date_to)
    except Exception as e:
        print(f"Database error: {e}", file=sys.stderr)
        return 1

    out = args.output or default_output_path(args.date_from, args.date_to)
    if not out.is_absolute():
        out = _ROOT / out

    build_pdf(out, rows, args.date_from, args.date_to)
    print(f"Wrote {out} ({len(rows)} record(s)).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
