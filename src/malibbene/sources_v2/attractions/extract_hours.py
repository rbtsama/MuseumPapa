"""Deterministic opening-hours extractor.

Output schema:

    {"hours": {"monday":"closed"|"10:00-17:00", ..., "sunday":...},
     "seasonal": {"start_month":int,"end_month":int,"note":str} | null,
     "source_phrase": short verbatim window,
     "note": optional}

Rules:
- Look for ranges like "Mon-Fri 10-5", "Wednesday-Monday 9:00am-4:00pm",
  "10am-5pm daily", "Closed Mondays", "Tuesday - Saturday 10:00 - 4:00".
- Convert 12h -> 24h.
- Detect seasonal openness ("Open May - October") and emit it.
- If absolutely nothing parses, fill all 7 days with "unknown".
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .extract_visitor_eligibility import html_to_text, _gather_html


_DAY_FULL = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}
_DAY_ABBR = {
    "mon": 0, "tue": 1, "tues": 1, "wed": 2, "weds": 2,
    "thu": 3, "thur": 3, "thurs": 3, "fri": 4, "sat": 5, "sun": 6,
}
_DAY_NAMES = {**_DAY_FULL, **_DAY_ABBR}
_DAY_IDX_TO_KEY = ["monday", "tuesday", "wednesday", "thursday", "friday",
                    "saturday", "sunday"]


def _parse_clock(token: str) -> str | None:
    """Parse '10am', '5:00pm', '14:30' etc to 'HH:MM'."""
    m = re.match(
        r"^\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm|noon|midnight)?\s*$",
        token.strip(), re.I,
    )
    if not m:
        return None
    h = int(m.group(1))
    mm = int(m.group(2) or 0)
    suffix = (m.group(3) or "").lower()
    if suffix == "noon":
        return "12:00"
    if suffix == "midnight":
        return "00:00"
    if suffix == "pm" and h < 12:
        h += 12
    if suffix == "am" and h == 12:
        h = 0
    if h > 23 or mm > 59:
        return None
    return f"{h:02d}:{mm:02d}"


_RANGE = re.compile(
    r"\b(?P<d1>\w+)\s*(?:-|–|—|to|through|–)\s*(?P<d2>\w+)\s+"
    r"(?P<t1>\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s*(?:-|–|—|to)\s*"
    r"(?P<t2>\d{1,2}(?::\d{2})?\s*(?:am|pm)?)",
    re.I,
)
_SINGLE = re.compile(
    r"\b(?P<d>\w+)\s+(?P<t1>\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s*(?:-|–|—|to)\s*"
    r"(?P<t2>\d{1,2}(?::\d{2})?\s*(?:am|pm)?)",
    re.I,
)
_CLOSED = re.compile(
    r"\bclosed\s+(?:on\s+)?(?P<d>\w+)s?\b",
    re.I,
)
_SEASONAL = re.compile(
    r"\bopen(?:s)?\s+(\w+)\s*(?:-|–|to|through)\s*(\w+)\b",
    re.I,
)

_MONTH = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _expand_day_range(d1: str, d2: str) -> list[int]:
    d1l = d1.lower().rstrip("s")
    d2l = d2.lower().rstrip("s")
    if d1l not in _DAY_NAMES or d2l not in _DAY_NAMES:
        return []
    a, b = _DAY_NAMES[d1l], _DAY_NAMES[d2l]
    if a <= b:
        return list(range(a, b + 1))
    # wrap-around
    return list(range(a, 7)) + list(range(0, b + 1))


def extract_hours(slug: str, raw_root: Path) -> dict[str, Any]:
    html = _gather_html(slug, raw_root)
    hours_map: dict[str, str] = {d: "unknown" for d in _DAY_IDX_TO_KEY}
    seasonal = None
    source_phrase = None

    if not html:
        return {"status": "ok", "extracted": {
            "hours": hours_map, "seasonal": seasonal,
            "source_phrase": source_phrase,
        }}

    text = html_to_text(html)

    # Day-range with hours
    for m in _RANGE.finditer(text):
        days = _expand_day_range(m.group("d1"), m.group("d2"))
        if not days:
            continue
        t1 = _parse_clock(m.group("t1"))
        t2 = _parse_clock(m.group("t2"))
        if not t1 or not t2:
            continue
        for di in days:
            if hours_map[_DAY_IDX_TO_KEY[di]] == "unknown":
                hours_map[_DAY_IDX_TO_KEY[di]] = f"{t1}-{t2}"
        if source_phrase is None:
            source_phrase = m.group(0)[:180]

    # Single day with hours
    for m in _SINGLE.finditer(text):
        d = m.group("d").lower().rstrip("s")
        if d not in _DAY_NAMES:
            continue
        t1 = _parse_clock(m.group("t1"))
        t2 = _parse_clock(m.group("t2"))
        if not t1 or not t2:
            continue
        di = _DAY_NAMES[d]
        if hours_map[_DAY_IDX_TO_KEY[di]] == "unknown":
            hours_map[_DAY_IDX_TO_KEY[di]] = f"{t1}-{t2}"
        if source_phrase is None:
            source_phrase = m.group(0)[:180]

    # Closed-on cues
    for m in _CLOSED.finditer(text):
        d = m.group("d").lower().rstrip("s")
        if d not in _DAY_NAMES:
            continue
        hours_map[_DAY_IDX_TO_KEY[_DAY_NAMES[d]]] = "closed"

    sm = _SEASONAL.search(text)
    if sm:
        m1 = _MONTH.get(sm.group(1).lower())
        m2 = _MONTH.get(sm.group(2).lower())
        if m1 and m2:
            seasonal = {"start_month": m1, "end_month": m2, "note": sm.group(0)}

    return {"status": "ok", "extracted": {
        "hours": hours_map, "seasonal": seasonal,
        "source_phrase": source_phrase,
    }}
