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


_DAYS = {"mon": "monday", "tue": "tuesday", "wed": "wednesday", "thu": "thursday",
         "fri": "friday", "sat": "saturday", "sun": "sunday"}
_TIME_RE = re.compile(r"(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m\.?", re.I)


def _t24(tok: str) -> str | None:
    """'10 AM'->'10:00', '5 PM'->'17:00', '10:30 PM'->'22:30'. Noon/Midnight too."""
    tok = tok.strip().lower()
    if tok in ("noon", "12 noon"):
        return "12:00"
    if tok in ("midnight",):
        return "00:00"
    m = _TIME_RE.search(tok)
    if not m:
        return None
    h = int(m.group(1)) % 12
    if m.group(3).lower() == "p":
        h += 12
    return f"{h:02d}:{int(m.group(2) or 0):02d}"


def _convert_hours(hours) -> dict | None:
    """Legacy hours {regular_hours:{mon:'10 AM – 5 PM', tue:'Closed'}} -> schema
    {monday:'10:00-17:00', tuesday:'closed', ...}. Returns None if unparseable."""
    if not isinstance(hours, dict):
        return None
    reg = hours.get("regular_hours")
    if not isinstance(reg, dict):
        return None
    out: dict[str, str] = {}
    for abbr, full in _DAYS.items():
        v = (reg.get(abbr) or "").strip()
        if not v:
            out[full] = "unknown"
        elif v.lower() in ("closed", "close"):
            out[full] = "closed"
        else:
            parts = re.split(r"\s*[–-]\s*", v, maxsplit=1)
            if len(parts) == 2:
                a, b = _t24(parts[0]), _t24(parts[1])
                out[full] = f"{a}-{b}" if a and b else "unknown"
            else:
                out[full] = "unknown"
    # all-unknown -> treat as no data
    return out if any(x != "unknown" for x in out.values()) else None


def _convert_prices(original_price) -> list[dict]:
    """Legacy original_price.age_pricing/identity_pricing/family/free_under_age
    -> schema prices list. Only emit audiences with a non-null price."""
    if not isinstance(original_price, dict):
        return []
    out: list[dict] = []
    SRC = "legacy original_price (2026-05-20 snapshot)"
    ap = original_price.get("age_pricing") or {}
    for aud in ("adult", "youth", "child", "senior"):
        info = ap.get(aud)
        if isinstance(info, dict) and info.get("price") is not None:
            rng = None
            if info.get("min_age") is not None or info.get("max_age") is not None:
                rng = {"min": info.get("min_age"), "max": info.get("max_age")}
            out.append({"audience": aud, "price": float(info["price"]),
                        "age_range": rng, "source_phrase": SRC})
    ip = original_price.get("identity_pricing") or {}
    for aud in ("student", "educator", "military"):
        info = ip.get(aud)
        if isinstance(info, dict) and info.get("price") is not None:
            out.append({"audience": aud, "price": float(info["price"]),
                        "age_range": None, "source_phrase": SRC})
    fam = original_price.get("family")
    if isinstance(fam, dict) and fam.get("price") is not None:
        out.append({"audience": "family", "price": float(fam["price"]),
                    "age_range": None, "source_phrase": SRC})
    fua = original_price.get("free_under_age")
    if isinstance(fua, int) and fua > 0:
        out.append({"audience": "child", "price": 0.0,
                    "age_range": {"min": 0, "max": fua - 1},
                    "source_phrase": f"free under age {fua} ({SRC})"})
    return out


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
            "prices": _convert_prices(r.get("original_price")),
            "hours": _convert_hours(r.get("hours")),
        }
    return out
