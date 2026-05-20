"""Assabet catalog scraper. Writes data/raw/assabet/catalog/<lib_id>.json."""
from __future__ import annotations
import json
import re
from pathlib import Path
from malibbene.common.http import fetch, fetch_and_save_html


# Real museum pass URLs look like:
#   .../museum-passes/by-museum/<slug>/
# where <slug> is NOT a reserved word ("by-museum", "by-date") and contains no
# query string (category filter links carry "?filter-categories[]=..." after
# /by-museum/). The parser pulls all such URLs from <a href> and <form action>
# then de-duplicates by slug.
_MUSEUM_URL_RE = re.compile(
    r'(?:href|action)="([^"]*?/museum-passes/by-museum/([a-z][a-z0-9\-]+)/)"',
    re.I,
)
_RESERVED_SLUGS = {"by-museum", "by-date"}


def parse_index_html(html: str, library_id: str) -> list[dict]:
    """Extract museum passes from an Assabet library's /museum-passes/ index.

    Each Assabet library page renders ALL its passes inline on one page; the
    canonical per-pass URL is /museum-passes/by-museum/<slug>/. We extract the
    slug + detail_url here and let scrape_library() fetch per-pass HTML for
    benefit text.
    """
    out = []
    seen = set()
    for url, slug in _MUSEUM_URL_RE.findall(html):
        if slug in _RESERVED_SLUGS or slug in seen:
            continue
        seen.add(slug)
        # Title: prettify slug as a fallback; per-pass HTML fetch will give the
        # real museum name via og:title or <h3>.
        title = slug.replace("-", " ").title()
        out.append({
            "library_id": library_id,
            "attraction_slug": slug,
            "title": title,
            "detail_url": url,
            "benefit_text": None,
            "source_phrases": [],
        })
    return out


def scrape_library(library_id: str, base_url: str, raw_root: Path) -> dict:
    """Full flow: fetch index -> fetch each pass detail -> write raw/assabet/catalog/<lib_id>.json"""
    index_url = base_url.rstrip("/") + "/museum-passes/"
    index_html = fetch(index_url)
    passes = parse_index_html(index_html, library_id)
    detail_dir = raw_root / "assabet" / "_html" / library_id
    for p in passes:
        html_path = fetch_and_save_html(p["detail_url"], detail_dir / f"{p['attraction_slug']}.html")
        text = html_path.read_text(encoding="utf-8")
        paras = re.findall(r"<p[^>]*>(.*?)</p>", text, re.S | re.I)
        clean = [re.sub(r"<[^>]+>", "", x).strip() for x in paras]
        clean = [c for c in clean if 10 < len(c) < 2000]
        p["benefit_text"] = "\n".join(clean[:8])
        p["source_phrases"] = clean
    out_path = raw_root / "assabet" / "catalog" / f"{library_id}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({
        "library_id": library_id, "index_url": index_url, "passes": passes,
    }, indent=2, ensure_ascii=False))
    return {"library_id": library_id, "n_passes": len(passes), "out": str(out_path)}
