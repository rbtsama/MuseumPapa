"""Scrape BPL LibCal museum-pass availability.

LibCal exposes an HTML calendar fragment at:

    GET https://bpl.libcal.com/pass/availability/institution
        ?museum=<bpl_pass_id>&date=<YYYY-MM-01>&digital=1&physical=1

Each ``<div class="day day-... day-YYYY-MM-DD ...">`` contains a span with one
of three classes that we collapse to two states:

  ``s-lc-pass-available`` → ``available``
  ``s-lc-pass-unavailable`` / ``s-lc-pass-not-yet-available`` → ``booked``

(Not-yet-available is BPL's monthly-release indicator — for the user it's
indistinguishable from booked at lookup time.)

Pass ids are read from ``data/raw/bpl/index.json`` (must be produced by
``malibbene.sources.bpl.index_page`` first).
"""

from __future__ import annotations

import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone, timedelta
from pathlib import Path

from malibbene.common import http, status

REPO_ROOT = Path(__file__).resolve().parents[4]
INDEX_PATH = REPO_ROOT / "data" / "raw" / "bpl" / "index.json"
OUT_PATH = REPO_ROOT / "data" / "raw" / "bpl" / "availability.json"

DAY_BLOCK_RE = re.compile(
    r'<div class="day day-[A-Z][a-z]+ day-(\d{4}-\d{2}-\d{2})([^"]*)"([\s\S]{1,2000}?)</div>\s*</div>'
)


def parse_calendar(html_body: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for m in DAY_BLOCK_RE.finditer(html_body):
        date_str, classes, body = m.group(1), m.group(2), m.group(3)
        if "other-month" in classes or "day-past" in classes:
            continue
        if (
            "s-lc-pass-available" in body
            and "s-lc-pass-unavailable" not in body
            and "s-lc-pass-not-yet-available" not in body
        ):
            out[date_str] = "available"
        else:
            out[date_str] = "booked"
    return out


def scrape_one(pass_id: str) -> tuple[str, dict[str, str], str]:
    today = date.today()
    months = [today.replace(day=1)]
    next_month = (months[0] + timedelta(days=32)).replace(day=1)
    months.append(next_month)
    cal: dict[str, str] = {}
    last_err: str | None = None
    for first in months:
        url = (
            f"https://bpl.libcal.com/pass/availability/institution"
            f"?museum={pass_id}&date={first.isoformat()}&digital=1&physical=1"
        )
        try:
            html_body = http.fetch(
                url,
                headers={
                    "X-Requested-With": "XMLHttpRequest",
                    "Referer": "https://bpl.libcal.com/passes/",
                },
            )
        except Exception as e:
            last_err = type(e).__name__
            continue
        cal.update(parse_calendar(html_body))
    if cal:
        return pass_id, cal, status.OK
    if last_err:
        return pass_id, cal, status.failed(last_err)
    return pass_id, cal, status.EMPTY


def main() -> int:
    if not INDEX_PATH.exists():
        print(
            "ERROR: data/raw/bpl/index.json missing — run "
            "malibbene.sources.bpl.index_page first.",
            file=sys.stderr,
        )
        return 2
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    pass_ids = [p["pass_id"] for p in index["passes"]]

    print(f"Scraping BPL availability for {len(pass_ids)} passes...", file=sys.stderr)
    summary = status.StatusSummary()
    passes: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        for pass_id, cal, st in pool.map(scrape_one, pass_ids):
            passes[pass_id] = {"status": st, "calendar": cal}
            summary.add(st)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(
            {
                "scraped_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "meta": {"status_summary": summary.to_dict()},
                "passes": passes,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    n_days = sum(len(p["calendar"]) for p in passes.values())
    print(
        f"  done: {len(passes)} passes, {n_days} day-slots "
        f"(ok={summary.ok} failed={sum(summary.failed.values())})",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
