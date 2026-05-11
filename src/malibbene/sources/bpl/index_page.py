"""Scrape BPL's LibCal pass listing + per-pass detail page.

Two-step:

1. Fetch ``https://bpl.libcal.com/passes`` → discover all 22+ pass ids.
2. Fetch each ``https://bpl.libcal.com/passes/<pass_id>`` → extract title,
   address, discount description, museum website, pass format.

Pass format is inferred from the title suffix (``(e-coupon)`` / ``(downloadable)``
/ ``(physical)``) and from the availability blurb. Mapping:

  - "(e-coupon)" / "downloadable via email" → ``digital``
  - "(physical)" / "Physical Pass Availability" only → ``physical-circ``
    (BPL physical passes are circulating; cardholder picks up + returns)

Output: ``data/raw/bpl/index.json``
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
OUT_DIR = REPO_ROOT / "data" / "raw" / "bpl"
OUT_PATH = OUT_DIR / "index.json"

LISTING_URL = "https://bpl.libcal.com/passes"
DETAIL_URL_TEMPLATE = "https://bpl.libcal.com/passes/{pass_id}"

PASS_ID_RE = re.compile(r"/passes/([a-f0-9]{12})")
TITLE_RE = re.compile(r'<h1 id="s-lc-public-pt"[^>]*>(.*?)</h1>', re.DOTALL)
ADDRESS_RE = re.compile(
    r's-lc-pass-address[^>]*>(.*?)<(?:/p>|a\s)', re.DOTALL | re.IGNORECASE
)
# Everything between the title's closing </div></div> wrapper and the
# "Passes Availability" section heading.
CONTENT_SECTION_RE = re.compile(
    r'id="s-lc-public-pd"[\s\S]*?<div class="col-sm-8">([\s\S]*?)<div class="s-lc-avail-content"',
    re.IGNORECASE,
)
P_TAG_RE = re.compile(r"<p[^>]*>([\s\S]*?)</p>", re.IGNORECASE)
WEBSITE_RE = re.compile(
    r'<a\s+[^>]*href="(https?://[^"]+)"[^>]*class="s-lc-museum-link"', re.IGNORECASE
)
AVAIL_DIGITAL_RE = re.compile(r"downloadable\s+via\s+email", re.IGNORECASE)
AVAIL_PHYSICAL_RE = re.compile(r"must\s+be\s+picked\s+up\s+at\s+the\s+library", re.IGNORECASE)

TAG_RE = re.compile(r"<[^>]+>")


def _strip_tags(s: str) -> str:
    return html_mod.unescape(re.sub(r"\s+", " ", TAG_RE.sub(" ", s))).strip()


DIGITAL_SUFFIX_RE = re.compile(
    r"\((e-coupon|e-ticket|downloadable|digital|digital coupon pass|promo code|coupon code)\)",
    re.IGNORECASE,
)
PHYSICAL_SUFFIX_RE = re.compile(r"\((physical|physical pass)\)", re.IGNORECASE)


def classify_pass_type(title: str, body_text: str) -> str:
    if PHYSICAL_SUFFIX_RE.search(title):
        return "physical-circ"
    if DIGITAL_SUFFIX_RE.search(title):
        return "digital"
    has_digital = bool(AVAIL_DIGITAL_RE.search(body_text))
    has_physical = bool(AVAIL_PHYSICAL_RE.search(body_text))
    if has_digital and not has_physical:
        return "digital"
    if has_physical and not has_digital:
        return "physical-circ"
    return "unknown"


def list_passes() -> tuple[list[str], str]:
    try:
        body = http.fetch(LISTING_URL)
    except Exception as e:
        return [], status.failed(type(e).__name__)
    ids = sorted(set(PASS_ID_RE.findall(body)))
    return ids, status.OK if ids else status.EMPTY


def parse_detail(pass_id: str, html_body: str) -> dict:
    record: dict = {"pass_id": pass_id, "url": DETAIL_URL_TEMPLATE.format(pass_id=pass_id)}

    tm = TITLE_RE.search(html_body)
    record["title_raw"] = _strip_tags(tm.group(1)) if tm else ""
    # Title minus the format suffix in parentheses
    if record["title_raw"]:
        record["museum_name"] = re.sub(r"\s*\([^)]*\)\s*$", "", record["title_raw"]).strip()

    am = ADDRESS_RE.search(html_body)
    if am:
        record["address"] = _strip_tags(am.group(1))

    wm = WEBSITE_RE.search(html_body)
    if wm:
        record["website"] = wm.group(1)

    # Description: all <p> blocks inside the public-pd content section,
    # minus the address paragraph (already captured separately).
    cs = CONTENT_SECTION_RE.search(html_body)
    if cs:
        section = cs.group(1)
        paragraphs = []
        for pm in P_TAG_RE.finditer(section):
            txt = _strip_tags(pm.group(1))
            if not txt or txt == record.get("address"):
                continue
            paragraphs.append(txt)
        record["description"] = " ".join(paragraphs)
    else:
        record["description"] = ""

    record["pass_type"] = classify_pass_type(record.get("title_raw", ""), html_body)

    if not record.get("museum_name"):
        record["status"] = status.failed("parse:no_title")
    elif not record.get("description"):
        record["status"] = status.failed("parse:no_description")
    else:
        record["status"] = status.OK
    return record


def scrape_one(pass_id: str) -> dict:
    url = DETAIL_URL_TEMPLATE.format(pass_id=pass_id)
    try:
        body = http.fetch(url)
    except Exception as e:
        return {
            "pass_id": pass_id,
            "url": url,
            "status": status.failed(type(e).__name__),
        }
    return parse_detail(pass_id, body)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("Listing BPL passes...", file=sys.stderr)
    ids, listing_status = list_passes()
    print(f"  found {len(ids)} pass ids ({listing_status})", file=sys.stderr)

    print(f"Fetching {len(ids)} detail pages...", file=sys.stderr)
    summary = status.StatusSummary()
    passes: list[dict] = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        for record in pool.map(scrape_one, ids):
            passes.append(record)
            summary.add(record["status"])

    OUT_PATH.write_text(
        json.dumps(
            {
                "scraped_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "url": LISTING_URL,
                "meta": {
                    "listing_status": listing_status,
                    "status_summary": summary.to_dict(),
                },
                "passes": passes,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(
        f"  done: ok={summary.ok} failed={sum(summary.failed.values())}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
