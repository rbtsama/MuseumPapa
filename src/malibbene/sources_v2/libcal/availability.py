"""LibCal availability scraper.

The LibCal "institution" calendar endpoint at
``https://<sub>.libcal.com/pass/availability/institution?museum=<pass_id>&date=<YYYY-MM-DD>``
returns an HTML fragment (NOT JSON, despite earlier guesses). Each day is
rendered as::

    <div class="day day-Mon day-2026-05-25 [day-past] [day-other-month]">
      <div class="day-number">
        <span class="s-lc-pass-availability s-lc-pass-<status>">N</span>
      </div>
    </div>

Where ``<status>`` is one of ``available | unavailable | closed | not-yet-available``.
``day-other-month`` cells pad the calendar grid for the previous / next month
(we drop them so we only emit days that actually belong to the requested month).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from malibbene.common.http import fetch

# Each day cell. Capture the full class string (so we can detect other-month
# padding) and the inner block (so we can pull the s-lc-pass-* status).
_DAY_RE = re.compile(
    r'<div class="(?P<cls>day\s+day-(?:Sun|Mon|Tue|Wed|Thu|Fri|Sat)\s+day-(?P<date>\d{4}-\d{2}-\d{2})[^"]*)">'
    r'(?P<body>.*?)</div>\s*</div>',
    re.S,
)
_STATUS_RE = re.compile(r"s-lc-pass-(available|unavailable|closed|not-yet-available)")


def build_availability_url(libcal_subdomain: str, pass_id: str, date: str) -> str:
    return (
        f"https://{libcal_subdomain}.libcal.com/pass/availability/institution"
        f"?museum={pass_id}&date={date}"
    )


def _classify(status_token: str) -> str:
    # Normalize to the same vocabulary the Assabet scraper uses so downstream
    # consumers (build/passes.py) see one shape.
    if status_token == "available":
        return "available"
    if status_token == "unavailable":
        return "booked"
    if status_token == "closed":
        return "closed"
    if status_token == "not-yet-available":
        return "unavailable"
    return "unavailable"


def parse_availability_html(html: str) -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    for m in _DAY_RE.finditer(html):
        cls = m.group("cls")
        if "day-other-month" in cls.split():
            continue
        date = m.group("date")
        if date in seen:
            continue
        sm = _STATUS_RE.search(m.group("body"))
        status = _classify(sm.group(1)) if sm else "unavailable"
        seen.add(date)
        out.append({"date": date, "status": status})
    out.sort(key=lambda d: d["date"])
    return out


def _month_starts(start_date: str, months_ahead: int) -> list[str]:
    """start_date + the 1st of each of the next `months_ahead` months."""
    from datetime import date as _d
    y, m, _ = (int(x) for x in start_date.split("-"))
    out = [start_date]
    for _ in range(months_ahead):
        m += 1
        if m > 12:
            m = 1
            y += 1
        out.append(f"{y:04d}-{m:02d}-01")
    return out


def scrape_availability(
    library_id: str,
    libcal_subdomain: str,
    pass_id: str,
    attraction_slug: str,
    start_date: str,
    raw_root: Path,
    months_ahead: int = 2,
) -> dict:
    # Fetch the start month + the next `months_ahead` months, merge by date.
    merged: dict[str, str] = {}
    last_url = None
    for ms in _month_starts(start_date, months_ahead):
        url = build_availability_url(libcal_subdomain, pass_id, ms)
        last_url = url
        try:
            body = fetch(
                url,
                headers={
                    "Accept": "text/html, */*; q=0.01",
                    "X-Requested-With": "XMLHttpRequest",
                    "Referer": f"https://{libcal_subdomain}.libcal.com/passes/{pass_id}",
                },
            )
        except Exception:
            continue
        for d in parse_availability_html(body):
            merged[d["date"]] = d["status"]
    days = [{"date": k, "status": v} for k, v in sorted(merged.items())]
    url = last_url
    out = raw_root / "libcal" / "availability" / library_id / f"{attraction_slug}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "library_id": library_id,
                "attraction_slug": attraction_slug,
                "pass_id": pass_id,
                "pass_url": url,
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
