"""Build final attractions.json from catalog + price + image + geo + hours enrichments."""
from __future__ import annotations

import datetime as dt

from malibbene.build.categories import canonicalize as canonicalize_categories
from malibbene.build.slug_canonical import canonical as canonical_slug


def _price_block(rec: dict | None) -> dict | None:
    if not rec or rec.get("status") != "ok":
        return None

    def _age_tier(value):
        return {"price": value, "min_age": None, "max_age": None} if value is not None else None

    def _identity_tier(value):
        return {"price": value, "requires": None} if value is not None else None

    return {
        "age_pricing": {
            "adult":  _age_tier(rec.get("adult")),
            "youth":  _age_tier(rec.get("youth")),
            "child":  _age_tier(rec.get("child")),
            "senior": _age_tier(rec.get("senior")),
            "free_under_age": rec.get("free_under_age"),
        },
        "identity_pricing": {
            "student":  _identity_tier(rec.get("student")),
            "educator": _identity_tier(rec.get("educator")),
            "military": _identity_tier(rec.get("military")),
        },
        "family": rec.get("family"),
        "notes": rec.get("notes"),
        "source_url": rec.get("source_url"),
    }


def _image_block(rec: dict | None) -> dict | None:
    if not rec or rec.get("status") != "ok":
        return None
    return {
        "og_image_url": rec.get("og_image_url"),
        "local_path": rec.get("local_path"),
    }


def _geo_block(rec: dict | None) -> dict | None:
    if not rec or not rec.get("ok"):
        return None
    return {"lat": rec["lat"], "lon": rec["lon"]}


def _hours_block(rec: dict | None) -> dict | None:
    if not rec:
        return None
    status = rec.get("status")
    if status == "varies":
        return {
            "status": "varies",
            "regular_hours": None,
            "notes": rec.get("notes"),
            "source_url": rec.get("source_url"),
        }
    if status == "seasonal":
        return {
            "status": "seasonal",
            "regular_hours": rec.get("regular_hours"),
            "notes": rec.get("notes"),
            "source_url": rec.get("source_url"),
        }
    if status != "ok":
        return None
    rh = rec.get("regular_hours")
    if not rh:
        return None
    return {
        "status": "ok",
        "regular_hours": rh,
        "notes": rec.get("notes"),
        "source_url": rec.get("source_url"),
    }


def _apply_description_fallback(entry: dict, desc_rec: dict | None) -> None:
    """Fill description/phone from data/raw/attraction_descriptions when catalog is empty."""
    if not desc_rec or desc_rec.get("status") != "ok":
        return
    if not entry.get("description") and desc_rec.get("description"):
        entry["description"] = desc_rec["description"]
    if not entry.get("phone") and desc_rec.get("phone"):
        entry["phone"] = desc_rec["phone"]


def build_attractions(catalog: dict, prices: dict, images: dict, geo: dict,
                       hours: dict | None = None,
                       descriptions: dict | None = None) -> dict:
    """Return {attractions: [...], _meta: {...}}.

    Args:
        catalog: parsed library_catalog.json (Task 1 output)
        prices: dict slug → parsed data/raw/attraction_prices/<slug>.json
        images: dict slug → parsed data/raw/attraction_images/<slug>.json
        geo: parsed data/structured/geo.json
        hours: dict slug → parsed data/raw/attraction_hours/<slug>.json (optional)
    """
    attr_geo = geo.get("attractions", {})
    hours = hours or {}
    descriptions = descriptions or {}
    accum: dict[str, dict] = {}
    for lib_id, lib_entry in catalog.get("libraries", {}).items():
        for raw_slug, p in lib_entry.get("passes", {}).items():
            slug = canonical_slug(raw_slug)
            entry = accum.setdefault(slug, {
                "slug": slug,
                "museum_name": p.get("museum_name", ""),
                "address": p.get("address", ""),
                "website": p.get("website", ""),
                "phone": p.get("phone"),
                "description": p.get("description"),
                "categories": [],            # canonical 7-class set (written below)
                "categories_raw": [],        # union of raw Assabet labels (kept for audit / debug)
                "legacy_slugs": [],
                "sources": [],
            })
            if raw_slug != slug and raw_slug not in entry["legacy_slugs"]:
                entry["legacy_slugs"].append(raw_slug)
            if lib_id not in entry["sources"]:
                entry["sources"].append(lib_id)
            for fld in ("museum_name", "address", "website", "phone", "description"):
                if not entry.get(fld) and p.get(fld):
                    entry[fld] = p[fld]
            for c in p.get("categories", []):
                if c not in entry["categories_raw"]:
                    entry["categories_raw"].append(c)

    # After accumulation, normalize raw labels → canonical 7-class set.
    for entry in accum.values():
        entry["categories"] = canonicalize_categories(entry["categories_raw"])

    def _lookup(d: dict, slug: str, legacy_slugs: list[str]):
        """Raw enrichment files are keyed by legacy slug; fall back through aliases."""
        if slug in d:
            return d[slug]
        for ls in legacy_slugs:
            if ls in d:
                return d[ls]
        return None

    out = []
    for slug, base in accum.items():
        legacy_aliases = base.get("legacy_slugs", [])
        _apply_description_fallback(base, _lookup(descriptions, slug, legacy_aliases))
        out.append({
            **base,
            "original_price": _price_block(_lookup(prices, slug, legacy_aliases)),
            "hero_image": _image_block(_lookup(images, slug, legacy_aliases)),
            "geo": _geo_block(_lookup(attr_geo, slug, legacy_aliases)),
            "hours": _hours_block(_lookup(hours, slug, legacy_aliases)),
        })

    return {
        "_meta": {
            "built_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "n_attractions": len(out),
            "n_with_price": sum(1 for x in out if x["original_price"]),
            "n_with_image": sum(1 for x in out if x["hero_image"]),
            "n_with_geo": sum(1 for x in out if x["geo"]),
            "n_with_hours": sum(1 for x in out if x["hours"]),
        },
        "attractions": out,
    }
