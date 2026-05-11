"""Scrape BPL LibCal museum-pass availability (no Playwright needed).

LibCal serves an HTML calendar fragment at:
    GET https://bpl.libcal.com/pass/availability/institution
        ?museum=<bpl_pass_id>&date=<YYYY-MM-01>&digital=0&physical=1

Each `<div class="day day-... day-YYYY-MM-DD ...">` contains a span with one of
three classes:
  s-lc-pass-available        -> at least one location has a pass available
  s-lc-pass-unavailable      -> all booked / no inventory
  s-lc-pass-not-yet-available-> booking window not open yet (BPL releases monthly)

We treat both `unavailable` and `not-yet-available` as booked from the user's
perspective (she can't book those days). Output schema mirrors availability.json:

  {
    "scraped_at": "2026-05-05T...",
    "data": {
      "<benefit_id>": { "bpl": { "YYYY-MM-DD": "available" | "booked" } }
    }
  }
"""

import json
import re
import sys
import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone, timedelta
from pathlib import Path

from bpl_id_map import BPL_PASS_ID

ROOT = Path(__file__).parent
OUT = ROOT / "bpl_availability.json"

DAY_BLOCK_RE = re.compile(
    r'<div class="day day-[A-Z][a-z]+ day-(\d{4}-\d{2}-\d{2})([^"]*)"([\s\S]{1,2000}?)</div>\s*</div>'
)


def fetch(url: str, timeout: int = 20) -> str:
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://bpl.libcal.com/passes/",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def parse_calendar(html: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for m in DAY_BLOCK_RE.finditer(html):
        date_str, classes, body = m.group(1), m.group(2), m.group(3)
        if "other-month" in classes or "day-past" in classes:
            continue
        if "s-lc-pass-available" in body and \
           "s-lc-pass-unavailable" not in body and \
           "s-lc-pass-not-yet-available" not in body:
            out[date_str] = "available"
        else:
            out[date_str] = "booked"
    return out


def scrape_one(benefit_id: str, pass_id: str) -> tuple[str, dict]:
    today = date.today()
    months = [today.replace(day=1)]
    next_month = (months[0] + timedelta(days=32)).replace(day=1)
    months.append(next_month)
    cal: dict[str, str] = {}
    for first in months:
        url = (
            f"https://bpl.libcal.com/pass/availability/institution"
            f"?museum={pass_id}&date={first.isoformat()}&digital=1&physical=1"
        )
        try:
            html = fetch(url)
        except Exception as e:
            print(f"  [err {e}] {benefit_id} {url}", file=sys.stderr)
            continue
        cal.update(parse_calendar(html))
    return benefit_id, cal


def main() -> None:
    print(f"Scraping BPL availability for {len(BPL_PASS_ID)} passes...")
    t0 = time.time()
    data: dict[str, dict[str, dict[str, str]]] = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(scrape_one, b, p) for b, p in BPL_PASS_ID.items()]
        for fut in as_completed(futures):
            benefit_id, cal = fut.result()
            if cal:
                data[benefit_id] = {"bpl": cal}

    OUT.write_text(json.dumps({
        "scraped_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "data": data,
    }, indent=2))
    n_dates = sum(len(d["bpl"]) for d in data.values())
    n_avail = sum(1 for d in data.values() for s in d["bpl"].values() if s == "available")
    print(f"Done in {time.time()-t0:.1f}s — {len(data)} passes, {n_dates} day-slots ({n_avail} available) → {OUT.name}")


if __name__ == "__main__":
    main()
