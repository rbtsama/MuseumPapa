"""Per (library, attraction) pass-format scraper.

Each Assabet library's master /museum-passes/by-museum/ page tags every pass
with a `<p class="museum-pass-pass-type">Pass Type: ...</p>` field. There are
exactly three values across all 13 libraries:

  - "Circulating Pass (must be picked up and returned to the branch)"
       => physical-circ   (pickup + return — most annoying)
  - "Coupon Pass (must be picked up from the branch, but does not require returning)"
       => physical-coupon (pickup only — mild)
  - "Printable/Digital Coupon Pass (link delivered by email)"
       => digital         (zero-hassle)

Writes pass_format.json:
{
  "scraped_at": "...",
  "data": { "<benefit_id>": { "<lib_id>": "physical-circ" | "physical-coupon" | "digital" } }
}
"""
import json
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from slug_map import LIB_DOMAIN, SLUG_MAP

ROOT = Path(__file__).parent
OUT = ROOT / "pass_format.json"

PASS_TYPE_MAP = {
    "circulating pass": "physical-circ",
    "coupon pass (must be picked up": "physical-coupon",
    "printable/digital coupon pass": "digital",
}


def fetch(url: str, timeout: int = 20) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def classify(text: str) -> str:
    low = text.strip().lower()
    for prefix, fmt in PASS_TYPE_MAP.items():
        if low.startswith(prefix):
            return fmt
    return "unknown"


BLOCK_START_RE = re.compile(r'id="location-summary-panel-([a-z0-9][a-z0-9\-]*)"')
PTYPE_RE = re.compile(
    r'museum-pass-pass-type[^>]*>(?:<strong>[^<]*</strong>)?\s*([^<]+)',
    re.IGNORECASE,
)


def scrape_library(lib_id: str, domain: str) -> tuple[str, dict[str, str]]:
    url = f"https://{domain}/museum-passes/by-museum/"
    try:
        html = fetch(url)
    except Exception as e:
        print(f"  [err {lib_id}] {e}", file=sys.stderr)
        return lib_id, {}

    starts = [(m.start(), m.group(1)) for m in BLOCK_START_RE.finditer(html)]
    out: dict[str, str] = {}
    for i, (start, slug) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else len(html)
        block = html[start:end]
        pm = PTYPE_RE.search(block)
        if not pm:
            continue
        fmt = classify(pm.group(1).strip())
        if fmt != "unknown":
            out[slug] = fmt
    return lib_id, out


def main() -> None:
    print(f"Scraping pass format for {len(LIB_DOMAIN)} libraries...")
    t0 = time.time()
    lib_slug_format: dict[str, dict[str, str]] = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        for lib_id, slug_to_fmt in pool.map(
            lambda kv: scrape_library(*kv), LIB_DOMAIN.items()
        ):
            lib_slug_format[lib_id] = slug_to_fmt

    out: dict[str, dict[str, str]] = {}
    counts = {"physical-circ": 0, "physical-coupon": 0, "digital": 0, "unknown": 0}
    for benefit_id, lib_slugs in SLUG_MAP.items():
        for lib_id, slug in lib_slugs.items():
            fmt = lib_slug_format.get(lib_id, {}).get(slug, "unknown")
            out.setdefault(benefit_id, {})[lib_id] = fmt
            counts[fmt] += 1

    OUT.write_text(json.dumps({
        "scraped_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "counts": counts,
        "data": out,
    }, indent=2))
    print(f"Done in {time.time()-t0:.1f}s — {counts} → {OUT.name}")


if __name__ == "__main__":
    main()
