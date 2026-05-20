"""MuseumKey catalog scraper (sources_v2).

MuseumKey serves a server-rendered HTML by-museum page at:
    https://www2.museumkey.com/ui/byMuseum/?code=<library_code>&branchID=<id>

Two themes exist:
  - v1 (e.g. Cohasset): museum name in ``class="museumButtonName"``, ``musID=N`` in
    the ``<a href>`` immediately preceding the name span.
  - MK2 (e.g. Hingham): museum name in ``class="mk2ButtonName"`` with a ``<p>``
    inner element, ``musID=N`` in a forward "Check Dates" link.

This module exposes the pure parser ``parse_museumkey_index`` (HTML -> list of
pass dicts) plus a ``scrape_library`` flow that writes
``data/raw/museumkey/catalog/<lib_id>.json``.

Note: availability calendars require a logged-in barcode, so museumkey only
emits a catalog snapshot here.
"""
from __future__ import annotations

import html as _html
import json
import re
from pathlib import Path

from malibbene.common.http import fetch

_NAME_RE_V1 = re.compile(
    r'class="museumButtonName"[^>]*>\s*([^<]+?)\s*</', re.DOTALL
)
_NAME_RE_MK2 = re.compile(
    r'class="mk2ButtonName"[^>]*>\s*<p[^>]*>\s*([^<]+?)\s*</p>', re.DOTALL
)
_MUSID_RE = re.compile(r"musID=(\d+)")
_SLUG_RE = re.compile(r"[^a-z0-9]+")

# Per-pass benefit text lives in a sibling <div ... id="detail<musid>"> block.
# Used by both themes (v1 Cohasset and MK2 Hingham).
_DETAIL_BLOCK_RE = re.compile(
    r'id="detail(\d+)"[^>]*>(.*?)(?=<a\s+data-bs-toggle="collapse"|'
    r'id="detail\d+"|<div\s+class="page_header"|</body>)',
    re.DOTALL | re.IGNORECASE,
)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
# Lines like "308 Congress Street Boston, MA 02210 617-426-6500 Get Directions"
# carry no benefit info; strip leading address+phone+Get Directions chunk so
# the downstream coupon extractor doesn't have to wade through it.
_LEAD_ADDRESS_RE = re.compile(
    # Match leading "address ... phone Get Directions". Phone allows optional
    # parens around the area code ("(781) 383-1434") and various separators.
    r"^.{0,250}?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b\s*(?:Get Directions\s*)?",
    re.IGNORECASE,
)
# MK2 (Hingham) layout interleaves "Visit museum website..." between Get
# Directions and the real benefit paragraph. Strip it from the *leading* edge.
_LEAD_VISIT_LINK_RE = re.compile(
    r"^\s*Visit museum website for more information\.?\s*",
    re.IGNORECASE,
)
_TRAILING_CTA_RE = re.compile(
    r"\s*(?:Check Dates|Learn More|Visit museum website for more information\.?)\s*$",
    re.IGNORECASE,
)


def _clean_benefit_text(raw_block: str) -> str:
    """Strip HTML, normalize whitespace, drop leading address/phone and CTA tail."""
    # Replace block boundaries with spaces so "</p><p>" doesn't fuse words.
    text = _TAG_RE.sub(" ", raw_block)
    text = _html.unescape(text)
    text = _WS_RE.sub(" ", text).strip()
    # Strip leading "<address> <phone> Get Directions"
    text = _LEAD_ADDRESS_RE.sub("", text).strip()
    # MK2: "Visit museum website..." may sit between the stripped address
    # block and the real benefit paragraph.
    text = _LEAD_VISIT_LINK_RE.sub("", text).strip()
    # Strip dangling CTA tail (may repeat)
    prev = None
    while prev != text:
        prev = text
        text = _TRAILING_CTA_RE.sub("", text).strip()
    return text


def _build_detail_map(html: str) -> dict[str, str]:
    """Map musid -> cleaned benefit text from all detail blocks on the page."""
    out: dict[str, str] = {}
    for m in _DETAIL_BLOCK_RE.finditer(html):
        musid = m.group(1)
        body = m.group(2)
        text = _clean_benefit_text(body)
        if text:
            out[musid] = text
    return out


def _slugify(name: str) -> str:
    s = _SLUG_RE.sub("-", name.lower()).strip("-")
    return s or "unknown"


def parse_museumkey_index(html: str, library_id: str) -> list[dict]:
    """Extract museum passes from a museumkey by-museum page.

    Returns a list of dicts with at minimum ``library_id``, ``title``,
    ``attraction_slug``, ``musid``, ``reserve_query``. De-dupes by slug.
    """
    out: list[dict] = []
    seen: set[str] = set()
    detail_map = _build_detail_map(html)

    def _emit(name: str, musid: str) -> None:
        slug = _slugify(name)
        if slug in seen:
            return
        seen.add(slug)
        benefit = detail_map.get(musid, "")
        entry = {
            "library_id": library_id,
            "title": name,
            "attraction_slug": slug,
            "musid": musid,
            "reserve_query": f"?musID={musid}",
            "benefit_text": benefit,
            "source_phrases": [benefit] if benefit else [],
        }
        out.append(entry)

    # Try v1 theme first; fall back to MK2.
    v1 = list(_NAME_RE_V1.finditer(html))
    if v1:
        for nm in v1:
            prefix = html[: nm.start()]
            m = list(_MUSID_RE.finditer(prefix))
            musid = m[-1].group(1) if m else ""
            name = _html.unescape(nm.group(1)).strip()
            if not name or not musid:
                continue
            _emit(name, musid)
        return out

    mk2 = list(_NAME_RE_MK2.finditer(html))
    for nm in mk2:
        ahead = html[nm.end():]
        m_fwd = _MUSID_RE.search(ahead)
        musid = m_fwd.group(1) if m_fwd else ""
        name = _html.unescape(nm.group(1)).strip()
        if not name or not musid:
            continue
        _emit(name, musid)
    return out


def scrape_library(library_id: str, base_url: str, raw_root: Path) -> dict:
    html = fetch(base_url)
    passes = parse_museumkey_index(html, library_id)
    out = raw_root / "museumkey" / "catalog" / f"{library_id}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {"library_id": library_id, "index_url": base_url, "passes": passes},
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return {"n_passes": len(passes), "out": str(out)}
