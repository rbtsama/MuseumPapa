"""Build final libraries.json from seeds + address/geo data."""
from __future__ import annotations

import datetime as dt


def _address_block(rec: dict | None) -> dict | None:
    if not rec or rec.get("status") != "ok":
        return None
    return {
        "street": rec.get("street"),
        "city": rec.get("city"),
        "state": rec.get("state"),
        "zip": rec.get("zip"),
    }


def _geo_block(rec: dict | None) -> dict | None:
    if not rec or not rec.get("ok"):
        return None
    return {"lat": rec["lat"], "lon": rec["lon"]}


def build_libraries(seeds: dict, addresses: dict, geo: dict) -> dict:
    """Return {libraries: [...], _meta: {...}}.

    Args:
        seeds: parsed config/library_seeds.json
        addresses: dict mapping lib_id → parsed data/raw/library_addresses/<lib_id>.json
        geo: parsed data/structured/geo.json
    """
    lib_geo = geo.get("libraries", {})
    out = []
    for s in seeds.get("libraries", []):
        lib_id = s["id"]
        out.append({
            "id": lib_id,
            "name": s.get("name", ""),
            "town": s.get("town", ""),
            "network": s.get("network", ""),
            "platform": s.get("platform", ""),
            "card_page": s.get("card_page", ""),
            "eligibility": s.get("non_resident_policy_initial", "unknown"),
            "supports_availability": s.get("supports_availability", False),
            "address": _address_block(addresses.get(lib_id)),
            "geo": _geo_block(lib_geo.get(lib_id)),
        })
    return {
        "_meta": {
            "built_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "n_libraries": len(out),
            "n_with_address": sum(1 for x in out if x["address"]),
            "n_with_geo": sum(1 for x in out if x["geo"]),
        },
        "libraries": out,
    }
