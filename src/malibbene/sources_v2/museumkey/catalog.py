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
            slug = _slugify(name)
            if slug in seen:
                continue
            seen.add(slug)
            out.append({
                "library_id": library_id,
                "title": name,
                "attraction_slug": slug,
                "musid": musid,
                "reserve_query": f"?musID={musid}",
            })
        return out

    mk2 = list(_NAME_RE_MK2.finditer(html))
    for nm in mk2:
        ahead = html[nm.end():]
        m_fwd = _MUSID_RE.search(ahead)
        musid = m_fwd.group(1) if m_fwd else ""
        name = _html.unescape(nm.group(1)).strip()
        if not name or not musid:
            continue
        slug = _slugify(name)
        if slug in seen:
            continue
        seen.add(slug)
        out.append({
            "library_id": library_id,
            "title": name,
            "attraction_slug": slug,
            "musid": musid,
            "reserve_query": f"?musID={musid}",
        })
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
