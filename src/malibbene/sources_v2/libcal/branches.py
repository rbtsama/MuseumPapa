"""LibCal branch (location) scraper.

BPL note
--------
``https://www.bpl.org/locations/`` is rendered client-side by the BiblioCommons
widget — the static HTML carries no branch list, so the original regex strategy
(matching ``<a href="/locations/<slug>/">``) yields 0 hits. The widget itself
calls the BiblioCommons gateway JSON endpoint:

    https://gateway.bibliocommons.com/v2/libraries/bpl/branches

which returns the canonical 28-branch roster (incl. Brighton, Central, etc.) as
JSON. We parse that response. The parser accepts the raw JSON text so the test
fixture stays a flat text file.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


# Fallback regex for any future LibCal-style site that *does* expose branches as
# anchor links to ``/locations/<slug>/``.
_BRANCH_HREF = re.compile(
    r'<a[^>]+href="/locations/([a-z0-9-]+)/"[^>]*>([^<]+)</a>', re.I
)


def _clean_bpl_name(raw: str) -> str:
    """Strip the ``BPL- ``/``BPL - `` prefix used by BiblioCommons."""
    name = raw.strip()
    # Common forms: "BPL- Brighton", "BPL - Central", "BPL- Central Delivery Desk"
    name = re.sub(r"^BPL\s*-\s*", "", name, flags=re.I)
    return name.strip()


def parse_bpl_locations(body: str) -> list[dict]:
    """Parse the BPL branch roster.

    Tries JSON (BiblioCommons gateway response) first; falls back to the LibCal
    anchor-link regex for any HTML input.
    """
    # JSON path (preferred)
    try:
        data = json.loads(body)
    except ValueError:
        data = None

    if isinstance(data, dict):
        entities = (data.get("entities") or {}).get("branches") or {}
        items = (data.get("branches") or {}).get("items") or list(entities.keys())
        seen: set[str] = set()
        out: list[dict] = []
        for code in items:
            ent = entities.get(str(code)) or {}
            raw_name = ent.get("name") or ""
            if not raw_name:
                continue
            name = _clean_bpl_name(raw_name)
            # Skip non-branch service points
            low = name.lower()
            if "delivery desk" in low:
                continue
            # Skip non-BPL partner libraries (Chelsea / Fisher / Malden) — they
            # appear in the same roster but are separate library_ids in v2.
            if not raw_name.lower().lstrip().startswith("bpl"):
                continue
            slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
            if slug in seen:
                continue
            seen.add(slug)
            out.append(
                {
                    "id": f"bpl-{slug}",
                    "library_id": "bpl",
                    "name": name,
                    "code": str(ent.get("code") or code),
                }
            )
        return out

    # HTML fallback
    seen2: set[str] = set()
    out2: list[dict] = []
    for slug, name in _BRANCH_HREF.findall(body):
        if slug in seen2:
            continue
        seen2.add(slug)
        out2.append(
            {"id": f"bpl-{slug}", "library_id": "bpl", "name": name.strip()}
        )
    return out2


def scrape_branches(library_id: str, locations_url: str, raw_root: Path):
    from malibbene.common.http import fetch

    body = fetch(locations_url)
    parser = {"bpl": parse_bpl_locations}.get(library_id)
    if parser is None:
        raise ValueError(f"no branch parser for {library_id}")
    branches = parser(body)
    out = raw_root / "libcal" / "branches" / f"{library_id}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps({"library_id": library_id, "branches": branches}, indent=2)
    )
    return {"n_branches": len(branches)}
