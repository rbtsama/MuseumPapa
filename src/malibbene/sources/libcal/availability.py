"""Scrape 30-day availability for every (LibCal library, pass) pair.

LibCal exposes an HTML calendar fragment at:

    GET https://<domain>/pass/availability/institution
        ?museum=<hex_museum_id>&date=<YYYY-MM-01>&digital=1&physical=1

Each ``<div class="day day-... day-YYYY-MM-DD ...">`` contains a span with one
of three classes that we collapse to two states:

  ``s-lc-pass-available`` → ``available``
  ``s-lc-pass-unavailable`` / ``s-lc-pass-not-yet-available`` → ``booked``

(Not-yet-available is BPL's monthly-release indicator — for the user it's
indistinguishable from booked at lookup time.)

The hex museum id comes from ``data/raw/libcal/index/<lib_id>.json``
(``museum_hex`` field, extracted from ``springyPage.museum`` in the detail
page). Some libraries' URL pass_id IS the hex (BPL); others use slugs whose
hex must be discovered separately (Cambridge).

Writes one file per library at ``data/raw/libcal/availability/<lib_id>.json``.
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
INDEX_DIR = REPO_ROOT / "data" / "raw" / "libcal" / "index"
OUT_DIR = REPO_ROOT / "data" / "raw" / "libcal" / "availability"
SEEDS_PATH = REPO_ROOT / "config" / "library_seeds.json"

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


def scrape_one(
    domain: str, museum_hex: str
) -> tuple[dict[str, str], str]:
    today = date.today()
    months = [today.replace(day=1)]
    next_month = (months[0] + timedelta(days=32)).replace(day=1)
    months.append(next_month)
    cal: dict[str, str] = {}
    last_err: str | None = None
    for first in months:
        url = (
            f"https://{domain}/pass/availability/institution"
            f"?museum={museum_hex}&date={first.isoformat()}&digital=1&physical=1"
        )
        try:
            html_body = http.fetch(
                url,
                headers={
                    "X-Requested-With": "XMLHttpRequest",
                    "Referer": f"https://{domain}/passes/",
                },
            )
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
            "scraped_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "meta": {"fetch_status": status.failed("missing_index")},
            "passes": {},
        }
    index = json.loads(index_path.read_text(encoding="utf-8"))

    # Each pass: prefer museum_hex from springyPage; fall back to pass_id when
    # the URL pass_id is itself hex (BPL, Braintree, Milton, parts of Brookline).
    targets: list[tuple[str, str]] = []
    for p in index["passes"]:
        slug = p.get("slug")
        if not slug:
            continue
        hex_id = p.get("museum_hex") or (
            p.get("pass_id", "") if re.fullmatch(r"[0-9a-f]+", p.get("pass_id", "")) else ""
        )
        if not hex_id:
            # Can't query availability without a hex id; mark as unknown.
            targets.append((slug, ""))
        else:
            targets.append((slug, hex_id))

    passes: dict[str, dict] = {}
    summary = status.StatusSummary()
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(
            pool.map(
                lambda sh: (sh[0], *(scrape_one(domain, sh[1]) if sh[1] else ({}, status.failed("no_hex")))),
                targets,
            )
        )
    for slug, cal, st in results:
        passes[slug] = {"status": st, "calendar": cal}
        summary.add(st)

    return lib_id, {
        "scraped_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "meta": {"fetch_status": status.OK, "status_summary": summary.to_dict()},
        "passes": passes,
    }


def load_libcal_targets() -> list[tuple[str, str]]:
    seeds = json.loads(SEEDS_PATH.read_text(encoding="utf-8"))
    return [
        (lib["id"], lib["domain"])
        for lib in seeds["libraries"]
        if lib["platform"] == "libcal" and lib.get("supports_availability", True)
    ]


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    targets = load_libcal_targets()
    print(f"Scraping availability for {len(targets)} LibCal libraries...", file=sys.stderr)
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
