"""Build final attractions.json from catalog + price + image + geo + hours enrichments."""
from __future__ import annotations

import datetime as dt


def _price_block(rec: dict | None) -> dict | None:
    if not rec or rec.get("status") != "ok":
        return None
    return {
        "adult": rec.get("adult"),
        "child": rec.get("child"),
        "senior": rec.get("senior"),
        "student": rec.get("student"),
        "family": rec.get("family"),
        "free_under_age": rec.get("free_under_age"),
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
    if not rec or rec.get("status") != "ok":
        return None
    rh = rec.get("regular_hours")
    if not rh:
        return None
    return {
        "regular_hours": rh,
        "notes": rec.get("notes"),
        "source_url": rec.get("source_url"),
    }


def build_attractions(catalog: dict, prices: dict, images: dict, geo: dict,
                       hours: dict | None = None) -> dict:
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
    accum: dict[str, dict] = {}
    for lib_id, lib_entry in catalog.get("libraries", {}).items():
        for slug, p in lib_entry.get("passes", {}).items():
            entry = accum.setdefault(slug, {
                "slug": slug,
                "museum_name": p.get("museum_name", ""),
                "address": p.get("address", ""),
                "website": p.get("website", ""),
                "categories": [],
                "sources": [],
            })
            if lib_id not in entry["sources"]:
                entry["sources"].append(lib_id)
            for fld in ("museum_name", "address", "website"):
                if not entry[fld] and p.get(fld):
                    entry[fld] = p[fld]
            for c in p.get("categories", []):
                if c not in entry["categories"]:
                    entry["categories"].append(c)

    out = []
    for slug, base in accum.items():
        out.append({
            **base,
            "original_price": _price_block(prices.get(slug)),
            "hero_image": _image_block(images.get(slug)),
            "geo": _geo_block(attr_geo.get(slug)),
            "hours": _hours_block(hours.get(slug)),
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
