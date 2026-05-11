"""Compute US federal holidays for the next 3 years.

Per BRD §6.1B (holiday closures), this is the baseline calendar to fall back
on when a museum's own site doesn't publish year-by-year closures. Many North
Shore attractions close on these days even when their regular hours would say
otherwise — Christmas, Thanksgiving, July 4, etc.

Output: ``data/us_holidays.json`` — flat list of ``{date, name, type}``.
"""

from __future__ import annotations

import json
import sys
from calendar import monthrange
from datetime import date, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
OUT_PATH = REPO_ROOT / "data" / "us_holidays.json"

MON, TUE, WED, THU, FRI, SAT, SUN = range(7)


def nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + timedelta(days=offset + (n - 1) * 7)


def last_weekday(year: int, month: int, weekday: int) -> date:
    _, last_day = monthrange(year, month)
    last = date(year, month, last_day)
    offset = (last.weekday() - weekday) % 7
    return last - timedelta(days=offset)


def observed(d: date) -> date:
    """Federal observance rule: Sat → Fri before, Sun → Mon after."""
    if d.weekday() == SAT:
        return d - timedelta(days=1)
    if d.weekday() == SUN:
        return d + timedelta(days=1)
    return d


def federal_holidays(year: int) -> list[dict]:
    h: list[dict] = []

    def add(d: date, name: str, type_: str = "federal", observed_for: date | None = None):
        h.append(
            {
                "date": d.isoformat(),
                "name": name,
                "type": type_,
                **({"observed_for": observed_for.isoformat()} if observed_for else {}),
            }
        )

    # Fixed-date holidays — emit both the actual date and (if it falls on a
    # weekend) the observed weekday.
    fixed = [
        (1, 1, "New Year's Day"),
        (6, 19, "Juneteenth"),
        (7, 4, "Independence Day"),
        (11, 11, "Veterans Day"),
        (12, 25, "Christmas Day"),
    ]
    for month, day, name in fixed:
        actual = date(year, month, day)
        add(actual, name)
        obs = observed(actual)
        if obs != actual:
            add(obs, f"{name} (observed)", observed_for=actual)

    # Floating holidays
    add(nth_weekday(year, 1, MON, 3), "Martin Luther King Jr. Day")
    add(nth_weekday(year, 2, MON, 3), "Presidents' Day")
    add(last_weekday(year, 5, MON), "Memorial Day")
    add(nth_weekday(year, 9, MON, 1), "Labor Day")
    add(nth_weekday(year, 10, MON, 2), "Columbus Day / Indigenous Peoples' Day")
    add(nth_weekday(year, 11, THU, 4), "Thanksgiving")
    # Day after Thanksgiving — not federal, but most museums close
    thanksgiving = nth_weekday(year, 11, THU, 4)
    add(thanksgiving + timedelta(days=1), "Black Friday", type_="commercial")
    # Christmas Eve & New Year's Eve — common partial-day closures
    add(date(year, 12, 24), "Christmas Eve", type_="common_closure")
    add(date(year, 12, 31), "New Year's Eve", type_="common_closure")

    return sorted(h, key=lambda x: x["date"])


def main() -> int:
    today = date.today()
    years = range(today.year, today.year + 3)
    all_h: list[dict] = []
    for y in years:
        all_h.extend(federal_holidays(y))
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps({"years": list(years), "holidays": all_h}, indent=2),
        encoding="utf-8",
    )
    print(f"Generated {len(all_h)} entries for years {list(years)} → {OUT_PATH}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
