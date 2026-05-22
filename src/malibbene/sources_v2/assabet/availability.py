"""Assabet museum-pass calendar availability scraper.

The Assabet calendar HTML encodes day status via CSS classes on each cell, e.g.::

    class="day day-mon day-2026-04-27 day-blank day-past day-no-openings"
    class="day day-tue day-2026-05-19 day-future day-has-openings"
    class="day day-wed day-2026-05-20 day-today day-has-openings"

We extract one record per real day cell (skipping ``day-blank`` placeholders that
just pad the calendar grid) and normalize the status to one of
``available | booked | unavailable | closed``.
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

from malibbene.common.http import fetch

_MONTH_NAMES = ["january", "february", "march", "april", "may", "june", "july",
                "august", "september", "october", "november", "december"]


def _month_urls(pass_url: str, months_ahead: int) -> list[str]:
    """Base pass URL (current month) + the next `months_ahead` month URLs.

    Assabet renders only ONE month per page; near month-end the current page has
    very few future days. The next month lives at
    ``<pass_url>/<year>-<monthname>/``. We fetch a forward window so the calendar
    has real lookahead.
    """
    base = pass_url.rstrip("/")
    urls = [pass_url]
    y, m = date.today().year, date.today().month
    for _ in range(months_ahead):
        m += 1
        if m > 12:
            m = 1
            y += 1
        urls.append(f"{base}/{y}-{_MONTH_NAMES[m-1]}/")
    return urls

# Match a day cell: capture the full class string so we can inspect modifiers.
_CELL_RE = re.compile(
    r'class="(?P<cls>day\s+day-(?:mon|tue|wed|thu|fri|sat|sun)\s+day-(?P<date>\d{4}-\d{2}-\d{2})[^"]*)"',
    re.I,
)


def _classify(cls: str) -> str | None:
    """Map a cell's class string to a normalized status, or None to skip."""
    tokens = set(cls.split())
    # day-blank cells are grid padding for prev/next month — not real days.
    if "day-blank" in tokens:
        return None
    if "day-has-openings" in tokens:
        return "available"
    if "day-past" in tokens:
        return "closed"
    if "day-unavailable" in tokens:
        return "unavailable"
    if "day-no-openings" in tokens:
        return "booked"
    # Fallback: unknown future state — treat as unavailable so we never lose the day.
    return "unavailable"


def parse_calendar_html(html: str) -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    for m in _CELL_RE.finditer(html):
        status = _classify(m.group("cls"))
        if status is None:
            continue
        date = m.group("date")
        if date in seen:
            continue
        seen.add(date)
        out.append({"date": date, "status": status})
    out.sort(key=lambda d: d["date"])
    return out


def scrape_availability(
    library_id: str,
    pass_url: str,
    raw_root: Path,
    attraction_slug: str,
    months_ahead: int = 2,
) -> dict:
    # Fetch the current month + the next `months_ahead` months, merge by date.
    merged: dict[str, str] = {}
    for url in _month_urls(pass_url, months_ahead):
        try:
            html = fetch(url)
        except Exception:
            continue  # a month page may 404 if not bookable that far out
        for d in parse_calendar_html(html):
            # don't let an earlier month's "past" cell overwrite a real status
            if d["date"] not in merged or d["status"] != "closed":
                merged[d["date"]] = d["status"]
    days = [{"date": k, "status": v} for k, v in sorted(merged.items())]
    out = raw_root / "assabet" / "availability" / library_id / f"{attraction_slug}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "library_id": library_id,
                "attraction_slug": attraction_slug,
                "pass_url": pass_url,
                "days": days,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return {
        "library_id": library_id,
        "attraction_slug": attraction_slug,
        "n_days": len(days),
    }
