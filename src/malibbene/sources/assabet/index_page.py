"""Scrape each Assabet library's master ``/museum-passes/by-museum/`` page.

Per pass, extracts:
- ``slug`` (e.g. ``boston-childrens-museum``)
- ``museum_name``, ``address``, ``phone``, ``website``, ``description`` (from
  the embedded ``application/ld+json`` block when present)
- ``categories`` (list of tag strings)
- ``pass_type_raw`` + ``pass_type`` (one of ``physical-circ`` /
  ``physical-coupon`` / ``digital`` / ``unknown``)
- ``benefits_text`` — the *Pass Benefits* free text, the headline input to
  Phase 2 LLM extraction (party limits, exclusions, residency rules, etc.)

Writes one file per library at ``data/raw/assabet/index/<lib_id>.json``.
"""

from __future__ import annotations

import html as html_mod
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from malibbene.common import http, status

REPO_ROOT = Path(__file__).resolve().parents[4]
OUT_DIR = REPO_ROOT / "data" / "raw" / "assabet" / "index"
SEEDS_PATH = REPO_ROOT / "config" / "library_seeds.json"

LOCATION_RE = re.compile(r'<div class="location museum museum-([a-z0-9][a-z0-9-]*)"')
JSONLD_RE = re.compile(
    r'<script type="application/ld\+json">(.+?)</script>', re.DOTALL
)
H3_RE = re.compile(r"<h3>([^<]+)</h3>")
H4_RE = re.compile(r"<h4>([^<]+)</h4>")
PASS_TYPE_RE = re.compile(
    r"museum-pass-pass-type[^>]*>(?:<strong>[^<]*</strong>)?\s*([^<]+)", re.IGNORECASE
)
CATEGORIES_RE = re.compile(
    r"museum-pass-categories[^>]*>.*?</strong>(.*?)</p>", re.DOTALL
)
CAT_ITEM_RE = re.compile(r">([^<]+)</a>")
BENEFITS_RE = re.compile(
    r"<h5>Pass Benefits</h5>\s*([\s\S]*?)(?=<div class=\"location-form-wrapper\"|<form\s|</div>\s*</div>\s*</div>)",
    re.IGNORECASE,
)
WEBSITE_ANCHOR_RE = re.compile(
    r'<a\s+href="(https?://[^"]+)"[^>]*aria-label="Visit\s+[^"]+\s+website"',
    re.IGNORECASE,
)

PASS_TYPE_MAP = [
    ("circulating pass", "physical-circ"),
    ("coupon pass (must be picked up", "physical-coupon"),
    ("printable/digital coupon pass", "digital"),
]


def _clean_text(s: str) -> str:
    s = html_mod.unescape(s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _classify_pass_type(text: str) -> str:
    low = text.strip().lower()
    for prefix, fmt in PASS_TYPE_MAP:
        if low.startswith(prefix):
            return fmt
    return "unknown"


def _split_blocks(html_body: str) -> list[tuple[str, str]]:
    """Return ``[(slug, block_html), ...]`` for each museum on the page."""
    starts = [(m.start(), m.group(1)) for m in LOCATION_RE.finditer(html_body)]
    out: list[tuple[str, str]] = []
    for i, (start, slug) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else len(html_body)
        out.append((slug, html_body[start:end]))
    return out


def _parse_jsonld(block: str) -> dict:
    m = JSONLD_RE.search(block)
    if not m:
        return {}
    raw = html_mod.unescape(m.group(1)).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def parse_pass_block(slug: str, block: str, page_url: str = "") -> dict:
    record: dict = {"slug": slug}
    if page_url:
        # Assabet renders all passes on one /by-museum/ page; per-pass deep-link
        # uses the location-class slug as a fragment hint.
        record["url"] = f"{page_url}#museum-{slug}"
    ld = _parse_jsonld(block)
    if ld:
        if ld.get("name"):
            record["museum_name"] = html_mod.unescape(ld["name"])
        record["address"] = ld.get("address")
        record["phone"] = ld.get("telephone")
        record["website"] = ld.get("url") or None
        if ld.get("description"):
            record["description"] = _clean_text(ld["description"])
    if not record.get("museum_name"):
        h = H3_RE.search(block) or H4_RE.search(block)
        if h:
            record["museum_name"] = _clean_text(h.group(1))

    # Fall back to the `[Visit ... website]` anchor when JSON-LD url is missing
    if not record.get("website"):
        wm = WEBSITE_ANCHOR_RE.search(block)
        if wm:
            record["website"] = wm.group(1)

    cm = CATEGORIES_RE.search(block)
    record["categories"] = (
        [_clean_text(c) for c in CAT_ITEM_RE.findall(cm.group(1))] if cm else []
    )

    pm = PASS_TYPE_RE.search(block)
    if pm:
        raw = _clean_text(pm.group(1))
        record["pass_type_raw"] = raw
        record["pass_type"] = _classify_pass_type(raw)
    else:
        record["pass_type_raw"] = ""
        record["pass_type"] = "unknown"

    bm = BENEFITS_RE.search(block)
    record["benefits_text"] = _clean_text(bm.group(1)) if bm else ""

    if not record.get("museum_name"):
        record["status"] = status.failed("parse:no_name")
    elif not record["benefits_text"] and record["pass_type"] == "unknown":
        record["status"] = status.failed("parse:empty_panel")
    else:
        record["status"] = status.OK
    return record


def scrape_library(lib_id: str, domain: str) -> tuple[str, dict]:
    url = f"https://{domain}/museum-passes/by-museum/"
    fetch_status = status.OK
    try:
        html_body = http.fetch(url)
    except Exception as e:
        return lib_id, {
            "url": url,
            "scraped_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "meta": {"fetch_status": status.failed(type(e).__name__)},
            "passes": [],
        }

    passes = [parse_pass_block(slug, block, url) for slug, block in _split_blocks(html_body)]
    summary = status.StatusSummary()
    for p in passes:
        summary.add(p["status"])
    return lib_id, {
        "url": url,
        "scraped_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "meta": {"fetch_status": fetch_status, "status_summary": summary.to_dict()},
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
    print(f"Scraping {len(targets)} Assabet libraries...", file=sys.stderr)
    total_ok = 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        for lib_id, data in pool.map(lambda lt: scrape_library(*lt), targets):
            (OUT_DIR / f"{lib_id}.json").write_text(
                json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            s = data["meta"].get("status_summary", {})
            total_ok += s.get("ok", 0)
            print(
                f"  {lib_id}: {len(data['passes'])} passes "
                f"(ok={s.get('ok', 0)} failed={sum(s.get('failed', {}).values())})",
                file=sys.stderr,
            )
    print(f"Total ok passes across libraries: {total_ok}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
