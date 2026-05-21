"""Deterministic opening-hours extractor.

Output schema:

    {"hours": {"monday":"closed"|"10:00-17:00", ..., "sunday":...},
     "seasonal": {"start_month":int,"end_month":int,"note":str} | null,
     "source_phrase": short verbatim window,
     "note": optional}

Rules:
- Look for ranges like "Mon-Fri 10-5", "Wednesday-Monday 9:00am-4:00pm",
  "10am-5pm daily", "Closed Mondays", "Tuesday - Saturday 10:00 - 4:00".
- Also handle real-world markup found in saved attraction HTML:
    * "Open Daily 10 am - 5 pm" / "Open daily from 9:00 am to 5:00 pm" /
      "7 Days per Week: 9:00 AM - 6:00PM"        -> all 7 days
    * time-before-day: "open 10AM - 3PM | Tuesday - Sunday",
      "10am - 4pm Open Daily"
    * per-day colon labels: "Monday: 11:00am-5:00pm", "Tuesday: Closed",
      "Monday : Closed", "Wednesday, 9:00 a.m. - 4:00 p.m."
    * closed ranges: "Sunday - Tuesday: CLOSED"
    * "a.m." / "p.m." with periods, en-dashes, em-dashes, vertical bars.
- Convert 12h -> 24h.
- Detect seasonal openness ("Open May - October") and emit it.
- If absolutely nothing parses, fill all 7 days with "unknown".

Honesty: only days literally stated get a value. "Open Daily 10-5" is a
literal statement about all 7 days, so all 7 are filled; a day that is never
mentioned stays "unknown".
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

# Dash characters used between days/times: hyphen, en-dash, em-dash, minus.
_DASH = r"[-‐-―−]"
# A clock token, e.g. "10", "10:30", "9 am", "5:00pm", "10 a.m.", "Noon".
_CLOCK = r"\d{1,2}(?::\d{2})?\s*(?:[ap]\.?\s*m\.?)?|noon|midnight"
# A day token allowing a trailing abbreviation period: "Mon", "Mon.", "Friday".
_DAY_TOK = r"[A-Za-z]+\.?"


def _norm_dashes(text: str) -> str:
    """Collapse the various dash glyphs to a plain hyphen for easier matching."""
    return re.sub(_DASH, "-", text)


def _parse_clock(token: str) -> str | None:
    """Parse '10am', '5:00pm', '14:30', '9 a.m.', 'Noon' etc to 'HH:MM'."""
    token = token.strip()
    low = token.lower()
    if low in ("noon", "12 noon", "12noon"):
        return "12:00"
    if low == "midnight":
        return "00:00"
    # Tolerate periods in am/pm: "9 a.m." -> "9 am"
    norm = re.sub(r"([ap])\.?\s*m\.?", r"\1m", low)
    m = re.match(
        r"^\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm|noon|midnight)?\s*$",
        norm, re.I,
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


def _has_meridiem(raw: str) -> bool:
    return bool(re.search(r"[ap]\.?\s*m", raw, re.I)) or raw.strip().lower() in (
        "noon", "midnight")


def _resolve_meridiem(t1: str | None, t2: str | None,
                      raw1: str, raw2: str) -> tuple[str | None, str | None]:
    """Infer missing am/pm so a day's window reads monotonically.

    Two real-world gaps this fixes:
    * start lacks am/pm but end has it ("10:00 - 5:00 pm"): borrow the end's
      meridiem for the start if it makes start < end.
    * end lacks am/pm and is a small hour <= start ("9:30 - 4"): a venue that
      opens in the morning and "closes" at an earlier clock value is really a
      PM closing, so bump the end into the afternoon.
    """
    if t1 is None or t2 is None:
        return t1, t2
    has1 = _has_meridiem(raw1)
    has2 = _has_meridiem(raw2)

    # Case A: start missing, end present.
    if not has1 and has2:
        end_pm = bool(re.search(r"p\.?\s*m", raw2, re.I))
        suffix = "pm" if end_pm else "am"
        cand = _parse_clock(f"{raw1.strip()} {suffix}")
        # Prefer borrowing the end's meridiem when (a) the naive AM reading is
        # non-monotonic, or (b) the end is PM and the naive AM start is an
        # implausibly early opening (< 7 a.m.) such as "1 - 5 pm" / "1 to 4 pm".
        start_hr = int(t1.split(":")[0])
        implausibly_early = end_pm and start_hr < 7
        if cand and cand < t2 and (not (t1 < t2) or implausibly_early):
            return cand, t2
        if t1 < t2:
            return t1, t2
        if cand and cand < t2:
            return cand, t2
        return t1, t2

    # Case B: end missing meridiem and is not after the start -> assume PM.
    if not has2 and t2 <= t1:
        eh, em = t2.split(":")
        ehi = int(eh)
        if 1 <= ehi <= 11:
            cand = f"{ehi + 12:02d}:{em}"
            if cand > t1:
                return t1, cand
    return t1, t2


_TIMES = re.compile(
    rf"(?P<t1>{_CLOCK})\s*{_DASH}\s*(?P<t2>{_CLOCK})|"
    rf"(?P<u1>{_CLOCK})\s+to\s+(?P<u2>{_CLOCK})|"
    rf"(?P<f1>{_CLOCK})\s+through\s+(?P<f2>{_CLOCK})",
    re.I,
)

# Day-range followed by a time range: "Tuesday - Sunday 9:30 am - 5:00 pm",
# "Tues-Sun Noon-4pm". The day range and times may be separated by ":", "|",
# "from", whitespace.
_RANGE = re.compile(
    rf"\b(?P<d1>{_DAY_TOK})\s*(?:{_DASH}|to|through)\s*(?P<d2>{_DAY_TOK})"
    rf"[\s:,|]*(?:from\s+)?"
    rf"(?P<t1>{_CLOCK})\s*(?:{_DASH}|to|through)\s*(?P<t2>{_CLOCK})",
    re.I,
)

# Time range followed by a day range: "open 10AM - 3PM | Tuesday - Sunday".
# Negative lookahead: don't treat a *closed* day-range ("Sunday - Tuesday:
# CLOSED") as the recipient of the preceding window's hours.
_RANGE_REV = re.compile(
    rf"(?P<t1>{_CLOCK})\s*(?:{_DASH}|to|through)\s*(?P<t2>{_CLOCK})"
    rf"\s*[|,]?\s*(?:open\s+)?"
    rf"\b(?P<d1>{_DAY_TOK})\s*(?:{_DASH}|to|through)\s*(?P<d2>{_DAY_TOK})\b"
    rf"(?!\s*[:,]?\s*closed)",
    re.I,
)

# "Weekends: 9:00 a.m. - 6:00 p.m." -> Saturday + Sunday.
_WEEKENDS = re.compile(
    rf"\bweekends?\b[\s:,|]*(?:from\s+)?"
    rf"(?P<t1>{_CLOCK})\s*(?:{_DASH}|to|through)\s*(?P<t2>{_CLOCK})",
    re.I,
)
# "Weekdays: 9 - 5" -> Monday..Friday.
_WEEKDAYS = re.compile(
    rf"\bweekdays?\b[\s:,|]*(?:from\s+)?"
    rf"(?P<t1>{_CLOCK})\s*(?:{_DASH}|to|through)\s*(?P<t2>{_CLOCK})",
    re.I,
)

# Two days joined by "and": "Friday and Saturday: 9 am - 5 pm",
# "Saturdays and Sundays from 9:30 - 5".
_AND_PAIR = re.compile(
    rf"\b(?P<d1>{_DAY_TOK})\s+and\s+(?P<d2>{_DAY_TOK})"
    rf"[\s:,|]*(?:from\s+)?"
    rf"(?P<t1>{_CLOCK})\s*(?:{_DASH}|to|through)\s*(?P<t2>{_CLOCK})",
    re.I,
)

# Single day with a time range: "Monday: 11:00am-5:00pm", "Wednesday, 9 am - 4 pm",
# "Monday 10am-5pm".
_SINGLE = re.compile(
    rf"\b(?P<d>{_DAY_TOK})[\s:,]*"
    rf"(?P<t1>{_CLOCK})\s*(?:{_DASH}|to|through)\s*(?P<t2>{_CLOCK})",
    re.I,
)

# "Open daily" / "open 7 days" / "7 days per week" / "every day" + a time range.
# Guard rails so this only fires on a genuine all-week claim:
#  * "daily schedule" is a per-day TABLE header, not an open-daily statement.
#  * "7 days during ... weeks" is a conditional/seasonal claim, not regular hours.
#  * the time must follow within a short gap that contains NO weekday name
#    (so "DAILY SCHEDULE MONDAY 10-5 TUESDAY CLOSED" never collapses to all-7).
_DAILY = re.compile(
    rf"\b(?:open\s+)?(?:daily(?!\s+schedule)|every\s+day|year[\s-]?round|"
    rf"7\s*days(?!\s+during)(?:\s+(?:a|per)\s+week)?|"
    rf"seven\s+days(?!\s+during)(?:\s+(?:a|per)\s+week)?)\b"
    rf"[\s:|,]*(?:from\s+)?"
    rf"(?P<t1>{_CLOCK})\s*(?:{_DASH}|to|through)\s*(?P<t2>{_CLOCK})",
    re.I,
)
# Time-range then "daily": "10am - 4pm Open Daily", "10am-5pm daily".
_DAILY_REV = re.compile(
    rf"(?P<t1>{_CLOCK})\s*(?:{_DASH}|to|through)\s*(?P<t2>{_CLOCK})"
    rf"\s*(?:open\s+)?\b(?:daily|every\s+day)\b",
    re.I,
)

# Closed cues.
_CLOSED_DAY = re.compile(  # "Closed Mondays", "closed on Sunday"
    rf"\bclosed\s+(?:on\s+)?(?P<d>{_DAY_TOK})s?\b",
    re.I,
)
_CLOSED_AFTER = re.compile(  # "Monday: Closed", "Monday, CLOSED", "Monday Closed"
    rf"\b(?P<d>{_DAY_TOK})\s*[:,]?\s+closed\b",
    re.I,
)
_CLOSED_RANGE = re.compile(  # "Sunday - Tuesday: CLOSED"
    rf"\b(?P<d1>{_DAY_TOK})\s*(?:{_DASH}|to|through)\s*(?P<d2>{_DAY_TOK})\s*[:,]?\s*closed\b",
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


_AGE_CTX = re.compile(
    r"\b(ages?|grades?|camp|kids?\s+ages?|years?\s+old|group\s+of|"
    r"sizes?|capacity|ratio|grade\s+levels?)\b",
    re.I,
)


def _looks_like_ages(m: "re.Match[str]", text: str) -> bool:
    """Reject a time pair that is really an age/grade/group-size range.

    Only triggers when BOTH endpoints are bare integers (no am/pm/colon) and
    the preceding context names ages/grades/camp/etc. "Camp for ages 8 - 12"
    must not become 08:00-12:00 hours.
    """
    raw1 = m.group("t1")
    raw2 = m.group("t2")
    bare = (re.fullmatch(r"\s*\d{1,2}\s*", raw1) and
            re.fullmatch(r"\s*\d{1,2}\s*", raw2))
    if not bare:
        return False
    pre = text[max(0, m.start() - 25): m.start()]
    return bool(_AGE_CTX.search(pre))


def _day_idx(token: str) -> int | None:
    t = token.lower().rstrip(".").rstrip("s")
    return _DAY_NAMES.get(t)


def _expand_day_range(d1: str, d2: str) -> list[int]:
    a = _day_idx(d1)
    b = _day_idx(d2)
    if a is None or b is None:
        return []
    if a <= b:
        return list(range(a, b + 1))
    # wrap-around (e.g. Saturday-Sunday handled by simple, Sunday-Tuesday wraps)
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

    text = _norm_dashes(html_to_text(html))

    def _set(di: int, val: str) -> None:
        if hours_map[_DAY_IDX_TO_KEY[di]] == "unknown":
            hours_map[_DAY_IDX_TO_KEY[di]] = val

    def _times(m: "re.Match[str]") -> tuple[str | None, str | None]:
        if _looks_like_ages(m, text):
            return None, None
        raw1 = m.group("t1")
        raw2 = m.group("t2")
        return _resolve_meridiem(_parse_clock(raw1), _parse_clock(raw2),
                                 raw1, raw2)

    def _note(m: "re.Match[str]") -> None:
        nonlocal source_phrase
        if source_phrase is None:
            source_phrase = m.group(0).strip()[:180]

    # 1. "Open daily ... 10 am - 5 pm" -> all 7 days. Run first so a venue's
    #    canonical "Open Daily" line wins over a more-specific co-located range
    #    that belongs to a *different* facility (e.g. USS Constitution: the
    #    Museum is open daily, the separately-listed Ship is Wed-Sun).
    for m in _DAILY.finditer(text):
        t1, t2 = _times(m)
        if not t1 or not t2:
            continue
        for di in range(7):
            _set(di, f"{t1}-{t2}")
        _note(m)
    for m in _DAILY_REV.finditer(text):
        t1, t2 = _times(m)
        if not t1 or not t2:
            continue
        for di in range(7):
            _set(di, f"{t1}-{t2}")
        _note(m)

    # 2. Day-range with hours: "Tuesday - Sunday 9:30 am - 5:00 pm"
    for m in _RANGE.finditer(text):
        days = _expand_day_range(m.group("d1"), m.group("d2"))
        if not days:
            continue
        t1, t2 = _times(m)
        if not t1 or not t2:
            continue
        for di in days:
            _set(di, f"{t1}-{t2}")
        _note(m)

    # 3. Time-range then day-range: "10AM - 3PM | Tuesday - Sunday"
    for m in _RANGE_REV.finditer(text):
        days = _expand_day_range(m.group("d1"), m.group("d2"))
        if not days:
            continue
        t1, t2 = _times(m)
        if not t1 or not t2:
            continue
        for di in days:
            _set(di, f"{t1}-{t2}")
        _note(m)

    # 4. Two days joined by "and": "Friday and Saturday: 9 am - 5 pm"
    for m in _AND_PAIR.finditer(text):
        d1i = _day_idx(m.group("d1"))
        d2i = _day_idx(m.group("d2"))
        if d1i is None or d2i is None:
            continue
        t1, t2 = _times(m)
        if not t1 or not t2:
            continue
        _set(d1i, f"{t1}-{t2}")
        _set(d2i, f"{t1}-{t2}")
        _note(m)

    # 5. "Weekdays: 9 - 5" / "Weekends: 9 - 6"
    for m in _WEEKDAYS.finditer(text):
        t1, t2 = _times(m)
        if not t1 or not t2:
            continue
        for di in range(0, 5):
            _set(di, f"{t1}-{t2}")
        _note(m)
    for m in _WEEKENDS.finditer(text):
        t1, t2 = _times(m)
        if not t1 or not t2:
            continue
        for di in (5, 6):
            _set(di, f"{t1}-{t2}")
        _note(m)

    # 6. Single day with hours: "Monday: 11:00am - 5:00pm", "Wednesday, 9 am - 4 pm"
    for m in _SINGLE.finditer(text):
        di = _day_idx(m.group("d"))
        if di is None:
            continue
        t1, t2 = _times(m)
        if not t1 or not t2:
            continue
        _set(di, f"{t1}-{t2}")
        _note(m)

    # 7. Closed ranges: "Sunday - Tuesday: CLOSED"
    for m in _CLOSED_RANGE.finditer(text):
        for di in _expand_day_range(m.group("d1"), m.group("d2")):
            _set(di, "closed")

    # 8. Closed single-day cues (both "Closed Monday" and "Monday: Closed").
    for m in _CLOSED_DAY.finditer(text):
        di = _day_idx(m.group("d"))
        if di is not None:
            _set(di, "closed")
    for m in _CLOSED_AFTER.finditer(text):
        di = _day_idx(m.group("d"))
        if di is not None:
            _set(di, "closed")

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
