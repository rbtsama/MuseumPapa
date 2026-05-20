from __future__ import annotations
import re
from datetime import date

_MONTHS = {"january":1,"february":2,"march":3,"april":4,"may":5,"june":6,
           "july":7,"august":8,"september":9,"october":10,"november":11,"december":12,
           "jan":1,"feb":2,"mar":3,"apr":4,"jun":6,"jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12}

_DATE_RE = re.compile(r"\b(" + "|".join(_MONTHS) + r")\s+(\d{1,2})", re.I)
_WEEKDAYS = {"sundays","mondays","tuesdays","wednesdays","thursdays","fridays","saturdays"}

def parse_blackout_phrase(text: str, recurring_out: bool = False):
    specific = []
    recurring = []
    for m, d in _DATE_RE.findall(text):
        specific.append({"month": _MONTHS[m.lower()], "day": int(d)})
    for w in _WEEKDAYS:
        if re.search(rf"\b{w}\b", text, re.I):
            recurring.append(w)
    if recurring_out:
        return specific, recurring
    return specific

_WEEKDAY_INDEX = {"mondays":0,"tuesdays":1,"wednesdays":2,"thursdays":3,
                  "fridays":4,"saturdays":5,"sundays":6}

def is_blackout_on(specific: list[dict], recurring: list[str], target: date) -> bool:
    for r in specific:
        if r["month"] == target.month and r["day"] == target.day:
            return True
    for w in recurring:
        if _WEEKDAY_INDEX.get(w) == target.weekday():
            return True
    return False
