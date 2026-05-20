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


_CAMBRIDGE_H3_TITLE = re.compile(
    r'<h3[^>]*class="[^"]*\btitle\b[^"]*"[^>]*>\s*([^<]+?)\s*</h3>', re.I
)
# Cambridge uses an H2 "Main Library" inside the same .libraryLocationList
# section. We anchor on the section to avoid matching unrelated H2/H3s.
_CAMBRIDGE_SECTION = re.compile(
    r'<section[^>]*class="[^"]*libraryLocationList[^"]*"[^>]*>(.*?)</section>',
    re.I | re.S,
)
_CAMBRIDGE_H2_MAIN = re.compile(
    r'<h2[^>]*>\s*(Main Library)\s*</h2>', re.I
)

# Brookline /visit/ page: each of the 3 branches is in its own <h1>.
# The opening "Visiting the Library" H1 is filtered by name allow-list because
# it's a generic page title, not a branch.
_BROOKLINE_H1 = re.compile(r'<h1[^>]*>(.*?)</h1>', re.S | re.I)
# Names known to be the actual Public Library of Brookline branches.
_BROOKLINE_KNOWN = {"brookline village", "coolidge corner", "putterham"}


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def parse_cambridge_locations(body: str) -> list[dict]:
    """Parse Cambridge Public Library locations.

    Source: ``https://www.cambridgema.gov/Departments/cambridgepubliclibrary/Locations``

    The page renders Main Library + 6 neighborhood branches inside a
    ``<section class="libraryLocationList">``. Main Library uses an ``<h2>``,
    each branch uses ``<h3 class="title">...Branch</h3>``.
    """
    section_match = _CAMBRIDGE_SECTION.search(body)
    scope = section_match.group(1) if section_match else body

    out: list[dict] = []
    seen: set[str] = set()
    # Main Library first (h2)
    if _CAMBRIDGE_H2_MAIN.search(scope):
        slug = "main"
        seen.add(slug)
        out.append(
            {
                "id": f"cambridge-{slug}",
                "library_id": "cambridge",
                "name": "Main Library",
            }
        )
    # Branches (h3 class="title")
    for m in _CAMBRIDGE_H3_TITLE.finditer(scope):
        name = re.sub(r"\s+", " ", m.group(1)).strip()
        # Only keep entries that look like a branch (avoid stray section titles
        # such as "Children's Room" / "Cambridge History Room" that share the
        # same H3 class on the Main Library card).
        if not name.lower().endswith("branch"):
            continue
        slug = _slugify(name.removesuffix(" Branch").removesuffix(" branch"))
        if not slug or slug in seen:
            continue
        seen.add(slug)
        out.append(
            {"id": f"cambridge-{slug}", "library_id": "cambridge", "name": name}
        )
    return out


def parse_brookline_locations(body: str) -> list[dict]:
    """Parse Public Library of Brookline locations.

    Source: ``https://brooklinelibrary.org/visit/``

    The page is server-rendered HTML; each of the 3 branches is a top-level
    ``<h1>`` (Brookline Village, Coolidge Corner, Putterham). The page also has
    an opening ``<h1>Visiting the Library</h1>`` we skip via an allow-list of
    known branch names.
    """
    out: list[dict] = []
    seen: set[str] = set()
    for m in _BROOKLINE_H1.finditer(body):
        # Strip any nested tags (e.g. <span style=...>) from the H1 inner HTML.
        name = re.sub(r"<[^>]+>", "", m.group(1))
        name = re.sub(r"\s+", " ", name).strip()
        if name.lower() not in _BROOKLINE_KNOWN:
            continue
        slug = _slugify(name)
        if slug in seen:
            continue
        seen.add(slug)
        out.append(
            {"id": f"brookline-{slug}", "library_id": "brookline", "name": name}
        )
    return out


def scrape_branches(library_id: str, locations_url: str, raw_root: Path):
    from malibbene.common.http import fetch

    body = fetch(locations_url)
    parser = {
        "bpl": parse_bpl_locations,
        "cambridge": parse_cambridge_locations,
        "brookline": parse_brookline_locations,
    }.get(library_id)
    if parser is None:
        raise ValueError(f"no branch parser for {library_id}")
    branches = parser(body)
    out = raw_root / "libcal" / "branches" / f"{library_id}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps({"library_id": library_id, "branches": branches}, indent=2)
    )
    return {"n_branches": len(branches)}
