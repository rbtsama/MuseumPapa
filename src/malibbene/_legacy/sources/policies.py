"""Fetch each library's *Get a Card* / borrower policy page (all 15 libraries).

Platform-agnostic: works for Assabet, LibCal (BPL), and Winchester. We save
the cleaned text body to ``data/raw/policies/<lib_id>.txt`` so Phase 2 (Claude
session) can extract:

- online_signup (yes/no)
- documents_required
- ecard_can_book_pass
- fine_policy
- family_quota_general

The ``card_page`` URL is read from ``config/library_seeds.json``. We accept
any library platform (assabet / libcal / winpublib) — the scraping logic is
domain-agnostic.
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

REPO_ROOT = Path(__file__).resolve().parents[3]
OUT_DIR = REPO_ROOT / "data" / "raw" / "policies"
SEEDS_PATH = REPO_ROOT / "config" / "library_seeds.json"
META_PATH = OUT_DIR / "_meta.json"

SCRIPT_STYLE_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"[ \t]+")
BLANK_LINE_RE = re.compile(r"\n{3,}")

# Anchor whose text or href hints at a library-card / borrowing page.
ANCHOR_RE = re.compile(
    r'<a\s+[^>]*href="([^"#?]+)(?:[?#][^"]*)?"[^>]*>([^<]{2,80})</a>',
    re.IGNORECASE,
)
CARD_KEYWORDS = re.compile(
    r"(get\s+a?\s*(library\s*)?card|library\s*card|borrow|borrower|member(ship)?|registration)",
    re.IGNORECASE,
)


def html_to_text(html_body: str) -> str:
    body = SCRIPT_STYLE_RE.sub(" ", html_body)
    body = TAG_RE.sub("\n", body)
    body = html_mod.unescape(body)
    body = WS_RE.sub(" ", body)
    lines = [ln.strip() for ln in body.splitlines()]
    body = "\n".join(ln for ln in lines if ln)
    body = BLANK_LINE_RE.sub("\n\n", body)
    return body.strip()


def _origin(url: str) -> str:
    m = re.match(r"(https?://[^/]+)", url)
    return m.group(1) if m else url


def _find_card_link(home_html: str, origin: str) -> str | None:
    for m in ANCHOR_RE.finditer(home_html):
        href, text = m.group(1), m.group(2)
        if not CARD_KEYWORDS.search(text) and not CARD_KEYWORDS.search(href):
            continue
        if href.startswith("http"):
            return href
        if href.startswith("//"):
            return "https:" + href
        if href.startswith("/"):
            return origin + href
        return origin + "/" + href
    return None


def _try_fetch(url: str) -> tuple[str, str] | None:
    try:
        body = http.fetch(url)
    except Exception:
        return None
    return url, body


def scrape_one(lib_id: str, seed_url: str) -> tuple[str, dict, str | None]:
    """Try seed URL, then fall back to discovering a card link from the homepage."""
    attempts: list[str] = []
    res = _try_fetch(seed_url)
    attempts.append(seed_url)
    if res is None or len(html_to_text(res[1])) < 300:
        origin = _origin(seed_url)
        home = _try_fetch(origin + "/")
        attempts.append(origin + "/")
        if home is not None:
            discovered = _find_card_link(home[1], origin)
            if discovered and discovered not in attempts:
                attempts.append(discovered)
                disc = _try_fetch(discovered)
                if disc is not None:
                    res = disc
    if res is None:
        return lib_id, {
            "url_tried": attempts,
            "status": status.failed("all_attempts_failed"),
            "size": 0,
        }, None
    final_url, body = res
    text = html_to_text(body)
    st = status.OK if len(text) >= 300 else status.EMPTY
    return lib_id, {
        "url_tried": attempts,
        "url_final": final_url,
        "status": st,
        "size": len(text),
    }, text


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    seeds = json.loads(SEEDS_PATH.read_text(encoding="utf-8"))
    libs = [(l["id"], l["card_page"]) for l in seeds["libraries"] if l.get("card_page")]

    print(f"Fetching card-policy pages for {len(libs)} libraries...", file=sys.stderr)
    meta: dict[str, dict] = {
        "scraped_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "libraries": {},
    }
    summary = status.StatusSummary()
    with ThreadPoolExecutor(max_workers=8) as pool:
        for lib_id, info, text in pool.map(lambda lt: scrape_one(*lt), libs):
            meta["libraries"][lib_id] = info
            summary.add(info["status"])
            if text:
                (OUT_DIR / f"{lib_id}.txt").write_text(text, encoding="utf-8")
            print(f"  {lib_id}: {info['status']} ({info['size']} chars)", file=sys.stderr)
    meta["status_summary"] = summary.to_dict()
    META_PATH.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
