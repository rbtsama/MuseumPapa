"""Build final passes.json — flat list of (library × attraction) pass entries."""
from __future__ import annotations

import datetime as dt


def build_passes(catalog: dict) -> dict:
    """Return {passes: [...], _meta: {...}}.

    Each element of `passes` is a (library_id, attraction_slug) row carrying
    the discount, pass_type, source_url, and availability calendar.
    """
    out = []
    for lib_id, lib_entry in catalog.get("libraries", {}).items():
        for slug, p in lib_entry.get("passes", {}).items():
            cal = p.get("calendar")
            out.append({
                "library_id": lib_id,
                "attraction_slug": slug,
                "pass_type": p.get("pass_type", "unknown"),
                "pass_type_raw": p.get("pass_type_raw", ""),
                "discount": {
                    "class": p.get("benefit_class", "unknown"),
                    "label": p.get("benefit_label", ""),
                    "raw": p.get("benefits_text", ""),
                },
                "source_url": p.get("source_url", ""),
                "availability": cal if cal else None,
            })
    return {
        "_meta": {
            "built_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "n_passes": len(out),
            "n_with_availability": sum(1 for x in out if x["availability"]),
        },
        "passes": out,
    }
