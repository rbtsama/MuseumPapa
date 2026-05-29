"""Phase A · Subpage discovery for source-block extraction.

For every attraction:
  1. Ensure data/raw/attractions/pages/<slug>.html exists (fetch from website if
     missing and a website is known).
  2. From the homepage HTML, pick up to 3 candidate deep-page URLs whose visible
     link text or URL path looks like a fit for tickets / admission / visit /
     plan-your-visit / pricing / hours / reservation / book / about. (Heuristic
     keyword scoring — the project's iron rule forbids LLM calls inside scripts;
     the real LLM evidence extraction happens in Phase B subagents.)
  3. Fetch each candidate (browser UA via common.http.fetch, follow redirects,
     save 200s only). Subpath slug in the filename is the last URL path segment,
     lowercased, with '-' separators.
  4. Skip if subpages/<slug>__<sub>.html already exists (idempotent).
  5. On 4xx/5xx, skip silently and proceed (retries=1, no extra retry).

For every library that has a card_page:
  - Fetch it to data/raw/libraries/_pages/<lib_id>.html.

Run:  python scripts/crawl_subpages.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from malibbene.common.http import fetch  # noqa: E402

ATTR_JSON = ROOT / "data" / "structured" / "attractions.json"
LIB_JSON = ROOT / "data" / "structured" / "libraries.json"
PAGES_DIR = ROOT / "data" / "raw" / "attractions" / "pages"
SUBPAGES_DIR = ROOT / "data" / "raw" / "attractions" / "subpages"
LIB_PAGES_DIR = ROOT / "data" / "raw" / "libraries" / "_pages"

# keyword -> weight; matched against both link text and the URL path.
KEYWORDS = {
    "admission": 6, "tickets": 6, "ticket": 5, "buy-tickets": 6,
    "pricing": 5, "prices": 5, "price": 4, "rates": 4, "fees": 4,
    "plan-your-visit": 6, "plan-a-visit": 6, "planyourvisit": 6,
    "visit": 4, "visitor": 4, "visiting": 4, "hours": 5, "opening": 4,
    "reservation": 5, "reservations": 5, "book": 4, "booking": 4,
    "about": 2, "info": 2, "directions": 2, "general-admission": 6,
}
MAX_CANDIDATES = 3

_HREF_RE = re.compile(r'<a\b[^>]*\bhref\s*=\s*["\']([^"\'#]+)["\'][^>]*>(.*?)</a>',
                      re.I | re.S)
_TAG_RE = re.compile(r"<[^>]+>")
_SRC_MARKER_RE = re.compile(r"<!--\s*source_url:\s*(\S+)\s*-->")


def _strip_marker_url(html: str) -> str | None:
    m = _SRC_MARKER_RE.search(html[:300])
    return m.group(1) if m else None


def _score_link(text: str, path: str) -> int:
    blob = f"{text} {path}".lower()
    score = 0
    for kw, w in KEYWORDS.items():
        if kw in blob:
            score += w
    return score


def _candidate_links(html: str, base_url: str) -> list[str]:
    """Return up to MAX_CANDIDATES same-host deep URLs, best keyword score first."""
    base_host = urlparse(base_url).netloc.lower().lstrip("www.")
    scored: dict[str, int] = {}
    for href, inner in _HREF_RE.findall(html):
        text = _TAG_RE.sub(" ", inner)
        text = re.sub(r"\s+", " ", text).strip()
        try:
            absu = urljoin(base_url, href)
        except Exception:
            continue
        pu = urlparse(absu)
        if pu.scheme not in ("http", "https"):
            continue
        host = pu.netloc.lower().lstrip("www.")
        if host != base_host:
            continue  # same-site only
        path = pu.path.rstrip("/")
        if not path or path == "/":
            continue  # skip the homepage itself
        # drop obvious non-content (files, feeds, wp-admin, etc.)
        if re.search(r"\.(pdf|jpg|jpeg|png|gif|svg|zip|ics)$", path, re.I):
            continue
        if re.search(r"(wp-admin|wp-login|/feed|/tag/|/category/|/author/)", path, re.I):
            continue
        score = _score_link(text, path)
        if score <= 0:
            continue
        clean = f"{pu.scheme}://{pu.netloc}{path}"
        if clean == base_url.rstrip("/"):
            continue
        if clean not in scored or score > scored[clean]:
            scored[clean] = score
    ranked = sorted(scored.items(), key=lambda kv: (-kv[1], kv[0]))
    return [u for u, _ in ranked[:MAX_CANDIDATES]]


def _sub_slug(url: str) -> str:
    seg = urlparse(url).path.rstrip("/").split("/")[-1]
    seg = re.sub(r"[^a-z0-9]+", "-", seg.lower()).strip("-")
    return seg or "page"


def _safe_fetch(url: str) -> str | None:
    """Single attempt (retries=1). Return body on 200, None on any failure."""
    try:
        return fetch(url, retries=1, timeout=30)
    except Exception as e:  # 4xx/5xx/network -> skip silently
        print(f"      skip ({type(e).__name__}: {e}) {url}")
        return None


def _save(out_path: Path, url: str, body: str) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(f"<!-- source_url: {url} -->\n" + body, encoding="utf-8")


def crawl_attractions() -> dict:
    attrs = json.loads(ATTR_JSON.read_text(encoding="utf-8"))["attractions"]
    stats = {"homepages_fetched": 0, "homepages_missing": 0, "subpages_fetched": 0,
             "subpages_skipped_exist": 0, "entities": len(attrs)}
    for a in attrs:
        slug = a["slug"]
        website = a.get("website")
        page_path = PAGES_DIR / f"{slug}.html"
        html = None
        if page_path.exists():
            html = page_path.read_text(encoding="utf-8", errors="replace")
            base = _strip_marker_url(html) or website
        elif website:
            print(f"[{slug}] homepage missing — fetching {website}")
            body = _safe_fetch(website)
            if body:
                _save(page_path, website, body)
                html = f"<!-- source_url: {website} -->\n" + body
                stats["homepages_fetched"] += 1
                base = website
            else:
                stats["homepages_missing"] += 1
                continue
        else:
            print(f"[{slug}] no homepage and no website — cannot crawl")
            stats["homepages_missing"] += 1
            continue

        base = (_strip_marker_url(html) or website or "").rstrip("/")
        if not base:
            continue
        cands = _candidate_links(html, base + "/")
        for url in cands:
            sub = _sub_slug(url)
            out = SUBPAGES_DIR / f"{slug}__{sub}.html"
            if out.exists():
                stats["subpages_skipped_exist"] += 1
                continue
            body = _safe_fetch(url)
            if body:
                _save(out, url, body)
                stats["subpages_fetched"] += 1
                print(f"   [{slug}] +subpage {sub}  <- {url}")
    return stats


def crawl_libraries() -> dict:
    libs = json.loads(LIB_JSON.read_text(encoding="utf-8"))["libraries"]
    stats = {"libs": len(libs), "fetched": 0, "skipped_exist": 0, "no_card_page": 0,
             "failed": 0}
    for l in libs:
        lib_id = l["id"]
        cp = l.get("card_page")
        if not cp:
            stats["no_card_page"] += 1
            continue
        out = LIB_PAGES_DIR / f"{lib_id}.html"
        if out.exists():
            stats["skipped_exist"] += 1
            continue
        body = _safe_fetch(cp)
        if body:
            _save(out, cp, body)
            stats["fetched"] += 1
            print(f"   [lib {lib_id}] card_page <- {cp}")
        else:
            stats["failed"] += 1
    return stats


def main() -> None:
    print("=== Phase A: attractions ===")
    a_stats = crawl_attractions()
    print("attractions:", json.dumps(a_stats))
    print("=== Phase A: libraries ===")
    l_stats = crawl_libraries()
    print("libraries:", json.dumps(l_stats))


if __name__ == "__main__":
    main()
