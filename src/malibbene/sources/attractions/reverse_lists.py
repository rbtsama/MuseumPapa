"""Scrape the 3 museums that publish their participating-library lists.

Per BRD §A.6, only 3 of ~14 surveyed MA museums publicly publish "which
libraries are part of our pass program":

  - Discovery Museum (Acton)  → high value for NorthShore (Kid-friendly)
  - JFK Library               → that-museum authority
  - MASS MoCA                 → that-museum authority

Used as a cross-check: if a North Shore library appears in the museum's list
but not in our Assabet/BPL data — or vice versa — flag it for review.

Output: ``data/raw/attractions/reverse_lists.json``
"""

from __future__ import annotations

import html as html_mod
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from malibbene.common import http, status

REPO_ROOT = Path(__file__).resolve().parents[4]
OUT_DIR = REPO_ROOT / "data" / "raw" / "attractions"
OUT_PATH = OUT_DIR / "reverse_lists.json"

SCRIPT_STYLE_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
TAG_RE = re.compile(r"<[^>]+>")

# A browser-like UA gets past Cloudflare-style filtering on these sites.
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

SOURCES = [
    {
        "id": "discovery-museum",
        "url": "https://www.discoveryacton.org/member-libraries",
    },
    {
        "id": "jfk-library",
        "url": "https://www.jfklibrary.org/visit-museum/visit/plan-your-trip/public-library-museum-pass-program",
    },
    {
        "id": "mass-moca",
        "url": "https://massmoca.org/library-pass-program/",
    },
]


def extract_text(html_body: str) -> str:
    body = SCRIPT_STYLE_RE.sub(" ", html_body)
    body = TAG_RE.sub("\n", body)
    body = html_mod.unescape(body)
    body = re.sub(r"[ \t]+", " ", body)
    lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
    return "\n".join(lines)


def extract_library_mentions(text: str) -> list[str]:
    """Heuristic: lines that look like 'X Library' or 'X Public Library'."""
    out: list[str] = []
    seen: set[str] = set()
    pattern = re.compile(r"^([A-Z][\w'.-]+(?:\s+[A-Z][\w'.-]+){0,5}\s+(?:Public\s+)?Library)\b")
    for line in text.split("\n"):
        m = pattern.match(line.strip())
        if not m:
            continue
        name = m.group(1).strip()
        if len(name) < 6 or len(name) > 80:
            continue
        if name not in seen:
            seen.add(name)
            out.append(name)
    return out


def scrape_one(source: dict) -> dict:
    url = source["url"]
    try:
        body = http.fetch(url, headers=BROWSER_HEADERS, timeout=30)
    except Exception as e:
        # Try Playwright fallback
        try:
            body = http.fetch(url, render_js=True, force=True, timeout=45)
        except Exception:
            return {
                "id": source["id"],
                "url": url,
                "status": status.failed(type(e).__name__),
                "library_mentions": [],
            }
    text = extract_text(body)
    mentions = extract_library_mentions(text)
    return {
        "id": source["id"],
        "url": url,
        "status": status.OK if mentions else status.EMPTY,
        "text_size": len(text),
        "library_mentions": mentions,
        "raw_text": text,
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Scraping {len(SOURCES)} reverse-list pages...", file=sys.stderr)
    summary = status.StatusSummary()
    results: list[dict] = []
    for src in SOURCES:
        r = scrape_one(src)
        results.append(r)
        summary.add(r["status"])
        print(
            f"  {r['id']}: {r['status']} (text={r.get('text_size', 0)} chars, "
            f"libraries={len(r['library_mentions'])})",
            file=sys.stderr,
        )
    OUT_PATH.write_text(
        json.dumps(
            {
                "scraped_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "meta": {"status_summary": summary.to_dict()},
                "sources": results,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
