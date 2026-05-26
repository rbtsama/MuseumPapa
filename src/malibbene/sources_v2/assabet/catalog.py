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
# Pass Type is NOT an <h5> heading — Assabet renders it in a
# `museum-pass-pass-type` element that sits just BEFORE the pass's by-museum
# URL (the benefit text is after it). Pattern ported from the proven legacy
# scraper (src/malibbene/_legacy/sources/assabet/index_page.py).
_PASS_TYPE_RE = re.compile(
    r"museum-pass-pass-type[^>]*>(?:<strong>[^<]*</strong>)?\s*([^<]+)", re.I
)
_PARA_RE = re.compile(r"<p[^>]*>(.*?)</p>", re.S | re.I)

# Raw pass-type text -> one of the three canonical pass types. Order matters:
# the more specific "coupon pass (must be picked up..." must precede a bare
# "coupon" match. Mirrors the legacy PASS_TYPE_MAP.
_PASS_TYPE_MAP = [
    ("circulating pass", "physical-circ"),
    ("coupon pass (must be picked up", "physical-coupon"),
    ("printable/digital coupon pass", "digital"),
]


def _classify_pass_type(text: str | None) -> str:
    low = (text or "").strip().lower()
    for prefix, fmt in _PASS_TYPE_MAP:
        if prefix in low:
            return fmt
    return "unknown"


def _strip(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s)).strip()


def _pass_windows(html: str, slug: str) -> tuple[str, str] | None:
    """Return (pre, post) HTML windows around a pass's by-museum URL anchor.

    `post` (the ~6000 chars AFTER the anchor) holds the Pass Benefits block.
    `pre` (the ~2500 chars BEFORE the anchor) holds the `museum-pass-pass-type`
    element, which Assabet renders ahead of the URL.
    """
    anchor = re.search(rf'/museum-passes/by-museum/{re.escape(slug)}/', html)
    if not anchor:
        return None
    return html[max(0, anchor.start() - 2500) : anchor.start()], html[anchor.end() : anchor.end() + 6000]


def parse_index_html(html: str, library_id: str) -> list[dict]:
    out = []
    seen = set()
    for url, slug in _MUSEUM_URL_RE.findall(html):
        if slug in _RESERVED_SLUGS or slug in seen:
            continue
        seen.add(slug)
        title = slug.replace("-", " ").title()

        windows = _pass_windows(html, slug)
        benefit_text = None
        pass_type_text = None
        phrases: list[str] = []
        if windows:
            pre, post = windows
            bm = _PASS_BENEFITS_RE.search(post)
            if bm:
                paras = _PARA_RE.findall(bm.group(1))
                phrases = [p for p in (_strip(x) for x in paras) if 5 < len(p) < 2000]
                if phrases:
                    benefit_text = "\n".join(phrases[:6])
            # The pass-type closest to the anchor (last match in `pre`) is this
            # pass's; earlier matches belong to the preceding pass card.
            tms = _PASS_TYPE_RE.findall(pre)
            if tms:
                pass_type_text = _strip(tms[-1])

        out.append({
            "library_id": library_id,
            "attraction_slug": slug,
            "title": title,
            "detail_url": url,
            "benefit_text": benefit_text,
            "pass_type_text": pass_type_text,
            "pass_type": _classify_pass_type(pass_type_text),
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
