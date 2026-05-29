from __future__ import annotations
import html
import json
import re
from pathlib import Path
from datetime import datetime, timezone
from malibbene.common.audit_overrides import load_overrides, apply_overrides
from malibbene.build.slug_canonical import canonical
from malibbene.build.legacy import legacy_attractions
from malibbene.build.categories import canonicalize as canonicalize_categories

def _read_json(p): return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

_WEEK_ORDER = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

def closed_days_from_hours(hours: dict | None) -> list[str]:
    """Weekly recurring closures derived from an hours dict (day -> "closed" /
    hours string / "unknown"). Returns canonical week order. Only "closed"
    counts — "unknown" is not a closure. (Holiday/seasonal closures aren't here.)"""
    if not hours:
        return []
    closed = {d for d, v in hours.items() if str(v).strip().lower() == "closed"}
    return [d for d in _WEEK_ORDER if d in closed] + [d for d in hours if d in closed and d not in _WEEK_ORDER]


# Page-title cruft to strip from raw <title> strings when no clean legacy name
# exists. e.g. "Peabody Essex Museum | World-Renowned Art Museum In Salem, MA",
# "Home - The Icon Museum and Study Center", "About | Foo".
_TITLE_TAIL_RE = re.compile(r"\s*[|–—\-]\s.*$")  # " | ...", " - ...", " – ..."
_TITLE_LEAD_RE = re.compile(r"^\s*(?:home|about|visit|welcome to)\s*[|\-:]\s*", re.I)


def _clean_name(raw: str | None) -> str | None:
    """Turn a raw HTML <title> into a presentable museum name.

    HTML-unescape, drop leading "Home -"/"About |" cruft, drop a trailing
    "| tagline" / "- tagline" segment, normalize ALL-CAPS to title case.
    Returns None for empty input (caller decides the fallback).
    """
    if not raw:
        return None
    name = html.unescape(raw).strip()
    if not name:
        return None
    name = _TITLE_LEAD_RE.sub("", name)
    # Strip a trailing separator + tagline, but keep it if that would empty the
    # name (e.g. a name that legitimately starts with a dash — rare).
    stripped = _TITLE_TAIL_RE.sub("", name).strip()
    if stripped:
        name = stripped
    name = re.sub(r"\s+", " ", name).strip()
    # ALL-CAPS -> Title Case (only if there are no lowercase letters at all).
    if name and name.upper() == name and re.search(r"[A-Z]", name):
        name = name.title()
    return name or None


def _catalog_titles(raw_root: Path) -> dict:
    """canonical_slug -> best museum name from the library catalogs.

    Attraction homepages don't always expose a clean <title>/og:title. The
    library pass catalogs always carry a human name for the museum, so they are
    a fallback display name. Keyed by CANONICAL slug; prefer the longer title.
    """
    best: dict[str, str] = {}
    for cat_f in raw_root.glob("*/catalog/*.json"):
        try:
            cat = json.loads(cat_f.read_text(encoding="utf-8"))
        except Exception:
            continue
        for p in cat.get("passes", []):
            slug = p.get("attraction_slug")
            title = (p.get("title") or "").strip()
            if not slug or not title:
                continue
            cslug = canonical(slug)
            cur = best.get(cslug)
            if cur is None or len(title) > len(cur):
                best[cslug] = title
    return best


def _pass_canonical_slugs(raw_root: Path) -> set[str]:
    """Every canonical attraction slug referenced by any pass in any catalog."""
    out: set[str] = set()
    for cat_f in raw_root.glob("*/catalog/*.json"):
        try:
            cat = json.loads(cat_f.read_text(encoding="utf-8"))
        except Exception:
            continue
        for p in cat.get("passes", []):
            s = p.get("attraction_slug")
            if s:
                out.add(canonical(s))
    return out


def _fetched_detail_slugs(raw_root: Path) -> dict[str, set[str]]:
    """canonical_slug -> {raw slug variants that have fetched detail}.

    The rebuild's raw extractions (pages/prices/hours/...) are keyed by the RAW
    catalog slug. Multiple raw variants can map to one canonical slug; we keep
    the variant list so we can look up whichever variant actually has data.
    """
    out: dict[str, set[str]] = {}
    pages_dir = raw_root / "attractions" / "pages"
    if pages_dir.exists():
        for meta_f in pages_dir.glob("*.meta.json"):
            try:
                slug = json.loads(meta_f.read_text(encoding="utf-8"))["slug"]
            except Exception:
                continue
            out.setdefault(canonical(slug), set()).add(slug)
    return out


def _first_ok(raw_root: Path, subdir: str, variants: list[str]):
    """Return the first OK extraction among `variants` under attractions/<subdir>."""
    for v in variants:
        d = _read_json(raw_root / "attractions" / subdir / f"{v}.json")
        if d and d.get("status") == "ok":
            return d
    return None


def collapse_blank_lines(s: str | None) -> str | None:
    """Drop blank lines INSIDE a source block — collapse runs of newlines (with
    any intervening whitespace) to a single newline, and trim per-line padding.
    The verbatim passage stays intact; it just reads tight, with no empty lines."""
    if not s:
        return s
    lines = [ln.strip() for ln in s.replace("\r\n", "\n").split("\n")]
    return "\n".join(ln for ln in lines if ln)


def _apply_source_blocks(a: dict, raw_root: Path) -> None:
    """Overlay verbatim source-block evidence (plan: source-block extraction).

    Reads data/raw/attractions/_source_blocks/<slug>.json and attaches the
    verbatim passages: prices matched by audience; reservation merged in place;
    hours / visitor_eligibility recorded under a['_evidence'][field]. A null
    field in the source-block file is honest "no passage found" — skipped here,
    not invented. Existing source_phrase fields are preserved as fallbacks.
    Blank lines inside each block are collapsed so the passage reads tight.
    """
    sb = _read_json(raw_root / "attractions" / "_source_blocks" / f"{a['slug']}.json")
    if not sb:
        return
    for p in a.get("prices", []):
        match = next((x for x in (sb.get("prices") or [])
                      if x and x.get("audience") == p.get("audience") and x.get("source_block")), None)
        if match:
            p["source_block"] = collapse_blank_lines(match.get("source_block"))
            p["source_url"] = match.get("source_url")
            p["source_confidence"] = match.get("source_confidence")
    rv = sb.get("reservation")
    if rv and rv.get("source_block") and isinstance(a.get("reservation"), dict):
        a["reservation"]["source_block"] = collapse_blank_lines(rv.get("source_block"))
        a["reservation"]["source_url"] = rv.get("source_url")
        a["reservation"]["source_confidence"] = rv.get("source_confidence")
    for fld in ("hours", "visitor_eligibility"):
        ev = sb.get(fld)
        if ev and ev.get("source_block"):
            a.setdefault("_evidence", {})[fld] = {
                "evidence": ev.get("source_phrase"),
                "block": collapse_blank_lines(ev.get("source_block")),
                "source": ev.get("source_url"),
                "source_confidence": ev.get("source_confidence"),
            }


def build_attractions(raw_root: Path, overrides_root: Path, out_path: Path) -> dict:
    overrides = load_overrides(overrides_root)
    legacy = legacy_attractions()
    catalog_names = _catalog_titles(raw_root)

    pass_slugs = _pass_canonical_slugs(raw_root)
    fetched = _fetched_detail_slugs(raw_root)

    # Universe of attraction records = every canonical slug a pass references,
    # UNION every canonical slug that has fetched detail. (The latter catches
    # detail-only entities that no current pass references.)
    all_slugs = sorted(pass_slugs | set(fetched.keys()))

    attractions = []
    for slug in all_slugs:
        leg = legacy.get(slug, {})
        # raw variants with fetched detail (e.g. "mfa-promo-code", "mfa").
        variants = sorted(fetched.get(slug, set()))

        # --- name: clean legacy museum_name, else cleaned catalog title, else
        #     cleaned fetched page title. Never null.
        name = leg.get("name") or _clean_name(catalog_names.get(slug))
        page_meta = None
        for v in variants:
            pm = _read_json(raw_root / "attractions" / "pages" / f"{v}.meta.json")
            if pm:
                page_meta = pm
                break
        if not name and page_meta:
            name = _clean_name(page_meta.get("title"))
        if not name:
            # honest last resort: humanize the slug so we never emit null.
            name = slug.replace("-", " ").title()

        a = {
            "slug": slug,
            "name": name,
            # website: rebuild meta first, else legacy.
            "website": (page_meta.get("url") if page_meta else None) or leg.get("website"),
            "phone": leg.get("phone"),
            "address": leg.get("address"),
            "geo": leg.get("geo"),
            "description": leg.get("description"),
            "categories": canonicalize_categories(leg.get("categories") or []),
            # hero_image: legacy URL preferred (rebuild meta og_image as fallback).
            "hero_image": leg.get("hero_image")
            or (page_meta.get("og_image") if page_meta else None),
            "prices": [],
            # Library-pass redemption model + note — populated via overrides from
            # verified per-museum research (P4-2). Default unknown.
            "booking_model": None,
            "booking_note": None,
            "closed_days": [],
            "sources": [],
        }

        # --- prices/hours/visitor_eligibility/reservation from the NEWER rebuild
        #     extractions, matched by whichever raw variant has the data. Fall
        #     back to the legacy snapshot (converted) when the rebuild has none
        #     — legacy covers far more of the long tail (prices 77, hours 97).
        prices = _first_ok(raw_root, "prices", variants)
        rebuilt_prices = prices["extracted"].get("prices", []) if prices else []
        a["prices"] = rebuilt_prices or list(leg.get("prices") or [])
        ve = _first_ok(raw_root, "visitor_eligibility", variants)
        if ve:
            a["visitor_eligibility"] = ve["extracted"]
        rv = _first_ok(raw_root, "reservation", variants)
        if rv:
            a["reservation"] = rv["extracted"]
        hr = _first_ok(raw_root, "hours", variants)
        rebuilt_hours = hr["extracted"].get("hours") if hr else None
        rebuilt_known = rebuilt_hours and any(
            v and v != "unknown" for v in rebuilt_hours.values())
        a["hours"] = rebuilt_hours if rebuilt_known else (leg.get("hours") or rebuilt_hours)
        a["closed_days"] = closed_days_from_hours(a["hours"])

        if page_meta and page_meta.get("url"):
            a["sources"] = [page_meta["url"]]
        elif a["website"]:
            a["sources"] = [a["website"]]

        a = apply_overrides(f"attraction:{slug}", a, overrides)
        # Recompute closed_days AFTER overrides so an hours override (e.g. a day
        # corrected to "closed") propagates to closed_days too.
        a["closed_days"] = closed_days_from_hours(a["hours"])
        _apply_source_blocks(a, raw_root)
        attractions.append(a)

    out = {"_meta": {"built_at": datetime.now(timezone.utc).isoformat(),
                     "n_attractions": len(attractions)},
           "attractions": attractions}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    return out
