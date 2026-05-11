"""Scrape Assabet Interactive availability for (library, attraction) pairs.

Outputs availability.json:
{
  "scraped_at": "2026-05-01T15:00:00",
  "data": {
    "<benefit_id>": {
      "<lib_id>": {
        "2026-05-03": "available" | "limited" | "booked" | "closed",
        ...
      }
    }
  }
}
"""

import json
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from slug_map import LIB_DOMAIN, SLUG_MAP

ROOT = Path(__file__).parent
OUT = ROOT / "availability.json"

DAY_RE = re.compile(
    r'class="day day-(?:sun|mon|tue|wed|thu|fri|sat) day-(\d{4}-\d{2}-\d{2})'
    r' (day-blank|day-past|day-today|day-future)?'
    r'(?: (day-no-openings|day-has-openings))?'
)
PARTIAL_RE = re.compile(r'time-partially-available')


def fetch(url: str, timeout: int = 15) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


DAY_TAG_RE = re.compile(r'<div class="day day-[a-z]+ day-(\d{4}-\d{2}-\d{2})([^"]*)"')
PARTIAL_DAY_RE = re.compile(
    r'<div class="day [^"]*day-(\d{4}-\d{2}-\d{2})[^"]*"[\s\S]{0,2000}?time-partially-available'
)


def parse_calendar(html: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for m in DAY_TAG_RE.finditer(html):
        date, classes = m.group(1), m.group(2)
        if "day-past" in classes or "day-blank" in classes:
            continue
        if "day-has-openings" in classes:
            out[date] = "available"
        elif "day-no-openings" in classes:
            out[date] = "booked"
    for m in PARTIAL_DAY_RE.finditer(html):
        date = m.group(1)
        if out.get(date) == "available":
            out[date] = "limited"
    return out


def scrape_one(lib_id: str, slug: str, benefit_id: str) -> tuple[str, str, dict]:
    domain = LIB_DOMAIN[lib_id]
    base = f"https://{domain}/museum-passes/by-museum/{slug}/"
    cal: dict[str, str] = {}
    for url in (base, base + "next/", base + "next/next/"):
        try:
            html = fetch(url)
        except Exception as e:
            print(f"  [err {e}] {benefit_id}@{lib_id} {url}", file=sys.stderr)
            break
        cal.update(parse_calendar(html))
    return benefit_id, lib_id, cal


def main() -> None:
    jobs = []
    for benefit_id, lib_slugs in SLUG_MAP.items():
        for lib_id, slug in lib_slugs.items():
            jobs.append((lib_id, slug, benefit_id))

    print(f"Scraping {len(jobs)} (library, attraction) pairs...")
    t0 = time.time()
    data: dict[str, dict[str, dict[str, str]]] = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(scrape_one, *j) for j in jobs]
        for fut in as_completed(futures):
            benefit_id, lib_id, cal = fut.result()
            if cal:
                data.setdefault(benefit_id, {})[lib_id] = cal

    OUT.write_text(json.dumps({
        "scraped_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "data": data,
    }, indent=2))
    n_dates = sum(len(d) for lib_data in data.values() for d in lib_data.values())
    print(f"Done in {time.time()-t0:.1f}s — {len(data)} attractions, {n_dates} day-slots → {OUT.name}")


if __name__ == "__main__":
    main()
