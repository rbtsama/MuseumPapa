"""Assabet catalog scraper. Writes data/raw/assabet/catalog/<lib_id>.json.

Important detail about Assabet markup: the /museum-passes/ index page renders
every pass inline with a <h5>Pass Benefits</h5><p>...</p> block. The per-pass
URLs (.../by-museum/<slug>/) point to JS-rendered calendar pages that DO NOT
contain benefit text — they only show the booking calendar. So we extract
benefit_text + source_phrases from the INDEX HTML, not from per-pass HTML.
"""
from __future__ import annotations
import json
import re
from pathlib import Path
from malibbene.common.http import fetch


_MUSEUM_URL_RE = re.compile(
    r'(?:href|action)="([^"]*?/museum-passes/by-museum/([a-z][a-z0-9\-]+)/)"',
    re.I,
)
_RESERVED_SLUGS = {"by-museum", "by-date"}

# Each pass section on the index lives inside a wrapper that contains the
# pass URL and (later) the Pass Benefits block. We locate the wrapper by
# anchoring on the slug match, then scan forward for the benefit/type blocks.
_PASS_BENEFITS_RE = re.compile(
    r"<h5[^>]*>\s*Pass\s+Benefits?\s*</h5>\s*(.+?)(?=<h5|</div>\s*</div>)",
    re.S | re.I,
)
_PASS_TYPE_RE = re.compile(
    r"<h5[^>]*>\s*Pass\s+Type[^<]*</h5>\s*(.+?)(?=<h5|</div>)",
    re.S | re.I,
)
_PARA_RE = re.compile(r"<p[^>]*>(.*?)</p>", re.S | re.I)


def _strip(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s)).strip()


def _slice_pass_section(html: str, slug: str) -> str | None:
    """Return the HTML window around a pass's section in the index.

    Assabet renders each pass in an `.entry`-like container. We anchor on the
    by-museum/<slug>/ URL and grab up to ~6000 chars forward — enough to cover
    the Pass Benefits + Pass Type blocks that follow.
    """
    anchor = re.search(
        rf'/museum-passes/by-museum/{re.escape(slug)}/', html
    )
    if not anchor:
        return None
    start = anchor.end()
    return html[start : start + 6000]


def parse_index_html(html: str, library_id: str) -> list[dict]:
    out = []
    seen = set()
    for url, slug in _MUSEUM_URL_RE.findall(html):
        if slug in _RESERVED_SLUGS or slug in seen:
            continue
        seen.add(slug)
        title = slug.replace("-", " ").title()

        section = _slice_pass_section(html, slug)
        benefit_text = None
        pass_type_text = None
        phrases: list[str] = []
        if section:
            bm = _PASS_BENEFITS_RE.search(section)
            if bm:
                paras = _PARA_RE.findall(bm.group(1))
                phrases = [p for p in (_strip(x) for x in paras) if 5 < len(p) < 2000]
                if phrases:
                    benefit_text = "\n".join(phrases[:6])
            tm = _PASS_TYPE_RE.search(section)
            if tm:
                pass_type_text = _strip(tm.group(1))

        out.append({
            "library_id": library_id,
            "attraction_slug": slug,
            "title": title,
            "detail_url": url,
            "benefit_text": benefit_text,
            "pass_type_text": pass_type_text,
            "source_phrases": phrases,
        })
    return out


def scrape_library(library_id: str, base_url: str, raw_root: Path) -> dict:
    """Fetch only the index page; benefit text comes from there."""
    index_url = base_url.rstrip("/") + "/museum-passes/"
    index_html = fetch(index_url)
    passes = parse_index_html(index_html, library_id)
    out_path = raw_root / "assabet" / "catalog" / f"{library_id}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(
            {"library_id": library_id, "index_url": index_url, "passes": passes},
            indent=2,
            ensure_ascii=False,
        )
    )
    return {"library_id": library_id, "n_passes": len(passes), "out": str(out_path)}
