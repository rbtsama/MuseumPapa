"""Scrape 30-day availability for every (library, pass) pair on Assabet.

Reads slugs from ``data/raw/assabet/index/<lib_id>.json`` (must have been
produced by ``malibbene.sources.assabet.index_page`` first) and walks each
library's per-museum calendar:

    https://<domain>/museum-passes/by-museum/<slug>/
    .../next/
    .../next/next/

Writes one file per library at ``data/raw/assabet/availability/<lib_id>.json``.
Per-day values: ``available`` / ``limited`` / ``booked``. Status field marks
fetch failures so downstream code can show "unknown" rather than "booked".
"""

from __future__ import annotations

import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from malibbene.common import http, status

REPO_ROOT = Path(__file__).resolve().parents[4]
INDEX_DIR = REPO_ROOT / "data" / "raw" / "assabet" / "index"
OUT_DIR = REPO_ROOT / "data" / "raw" / "assabet" / "availability"
SEEDS_PATH = REPO_ROOT / "config" / "library_seeds.json"

DAY_TAG_RE = re.compile(
    r'<div class="day day-[a-z]+ day-(\d{4}-\d{2}-\d{2})([^"]*)"'
)
PARTIAL_DAY_RE = re.compile(
    r'<div class="day [^"]*day-(\d{4}-\d{2}-\d{2})[^"]*"[\s\S]{0,2000}?time-partially-available'
)


def parse_calendar(html_body: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for m in DAY_TAG_RE.finditer(html_body):
        date, classes = m.group(1), m.group(2)
        if "day-past" in classes or "day-blank" in classes:
            continue
        if "day-has-openings" in classes:
            out[date] = "available"
        elif "day-no-openings" in classes:
            out[date] = "booked"
    for m in PARTIAL_DAY_RE.finditer(html_body):
        date = m.group(1)
        if out.get(date) == "available":
            out[date] = "limited"
    return out


def scrape_one(
    domain: str, slug: str
) -> tuple[dict[str, str], str]:
    """Return ``(date_map, status)`` for a single (library, pass) pair."""
    base = f"https://{domain}/museum-passes/by-museum/{slug}/"
    cal: dict[str, str] = {}
    last_err: str | None = None
    for url in (base, base + "next/", base + "next/next/"):
        try:
            html_body = http.fetch(url)
        except Exception as e:
            last_err = type(e).__name__
            continue
        cal.update(parse_calendar(html_body))
    if cal:
        return cal, status.OK
    if last_err:
        return cal, status.failed(last_err)
    return cal, status.EMPTY


def scrape_library(lib_id: str, domain: str) -> tuple[str, dict]:
    index_path = INDEX_DIR / f"{lib_id}.json"
    if not index_path.exists():
        return lib_id, {
            "url": None,
            "scraped_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "meta": {"fetch_status": status.failed("missing_index")},
            "passes": {},
        }
    index = json.loads(index_path.read_text(encoding="utf-8"))
    slugs = [
        p["slug"] for p in index["passes"]
        if not str(p.get("status", "")).startswith("failed")
    ]

    passes: dict[str, dict] = {}
    summary = status.StatusSummary()
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda s: (s, *scrape_one(domain, s)), slugs))
    for slug, cal, st in results:
        passes[slug] = {"status": st, "calendar": cal}
        summary.add(st)

    return lib_id, {
        "scraped_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "meta": {"fetch_status": status.OK, "status_summary": summary.to_dict()},
        "passes": passes,
    }


def load_assabet_targets() -> list[tuple[str, str]]:
    seeds = json.loads(SEEDS_PATH.read_text(encoding="utf-8"))
    return [
        (lib["id"], lib["domain"])
        for lib in seeds["libraries"]
        if lib["platform"] == "assabet"
    ]


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    targets = load_assabet_targets()
    print(f"Scraping availability for {len(targets)} Assabet libraries...", file=sys.stderr)
    for lib_id, domain in targets:
        _, data = scrape_library(lib_id, domain)
        (OUT_DIR / f"{lib_id}.json").write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        s = data["meta"].get("status_summary", {})
        n_days = sum(len(p["calendar"]) for p in data["passes"].values())
        print(
            f"  {lib_id}: {len(data['passes'])} passes, {n_days} day-slots "
            f"(ok={s.get('ok', 0)} failed={sum(s.get('failed', {}).values())})",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
