"""Loaders for the legacy archive (`data/_legacy/<date>/`).

The 2026-05-20 data-rebuild rewrote the build pipeline and dropped detail the
old data carried (library + attraction geo/address, attraction
phone/description/categories, clean museum names). Those values were never
re-scraped — they live in the legacy archive and we recover them here.

HONESTY: these loaders only surface values that exist in the archive. They
never fabricate. Missing values come back as None / empty.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

_LEGACY_DIR = (
    Path(__file__).resolve().parents[3] / "data" / "_legacy" / "2026-05-20"
)

# "1 Central Wharf, Boston, MA 02110"  /  "...Suite 900, Boston, MA 02114-2104"
_ADDR_TAIL_RE = re.compile(
    r"^(?P<street>.+),\s*(?P<city>[^,]+),\s*(?P<state>[A-Z]{2})\s+(?P<zip>\d{5}(?:-\d{4})?)\s*$"
)


def _parse_address(raw: str | None) -> dict | None:
    """Parse a legacy free-text address string into the Address schema shape.

    Honest fallback: if the trailing "City, ST ZIP" pattern doesn't match, keep
    whatever we have in `street` rather than guessing city/state/zip. A bare
    state token like "MA" is too thin to be useful — drop it.
    """
    if not raw or not isinstance(raw, str):
        return None
    raw = raw.strip()
    if not raw or raw == "MA":
        return None
    m = _ADDR_TAIL_RE.match(raw)
    if m:
        z = m.group("zip")
        return {
            "street": m.group("street").strip(),
            "city": m.group("city").strip(),
            "state": m.group("state"),
            "zip": z[:5],  # schema zip is 5-digit; keep the base ZIP
        }
    # Couldn't confidently split — keep the full string as street, leave the
    # rest empty (honest: we don't invent a city/state/zip).
    return {"street": raw, "city": None, "state": None, "zip": None}


def _hero_url(hero) -> str | None:
    """Legacy hero_image is a dict {local_path, og_image_url}; schema wants a
    URL string. Prefer the og_image_url."""
    if isinstance(hero, dict):
        return hero.get("og_image_url") or None
    if isinstance(hero, str):
        return hero or None
    return None


@lru_cache(maxsize=1)
def legacy_libraries() -> dict[str, dict]:
    """{library_id: {geo, address}} from the legacy libraries archive."""
    f = _LEGACY_DIR / "libraries.json"
    if not f.exists():
        return {}
    data = json.loads(f.read_text(encoding="utf-8"))
    records = data["libraries"] if isinstance(data, dict) else data
    out: dict[str, dict] = {}
    for r in records:
        lid = r.get("id")
        if not lid:
            continue
        out[lid] = {"geo": r.get("geo"), "address": r.get("address")}
    return out


@lru_cache(maxsize=1)
def legacy_attractions() -> dict[str, dict]:
    """{canonical_slug: enrichment} from the legacy attractions archive.

    enrichment = {name, geo, address, phone, description, categories,
    hero_image, website}. `address` is parsed into the Address schema shape.
    """
    f = _LEGACY_DIR / "attractions.json"
    if not f.exists():
        return {}
    data = json.loads(f.read_text(encoding="utf-8"))
    records = data["attractions"] if isinstance(data, dict) else data
    out: dict[str, dict] = {}
    for r in records:
        slug = r.get("slug")
        if not slug:
            continue
        out[slug] = {
            "name": (r.get("museum_name") or "").strip() or None,
            "geo": r.get("geo"),
            "address": _parse_address(r.get("address")),
            "phone": r.get("phone"),
            "description": r.get("description"),
            "categories": list(r.get("categories") or []),
            "hero_image": _hero_url(r.get("hero_image")),
            "website": r.get("website"),
        }
    return out
