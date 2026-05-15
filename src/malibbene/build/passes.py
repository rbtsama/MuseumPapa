"""Build final passes.json — flat list of (library × attraction) pass entries."""
from __future__ import annotations

import datetime as dt


def _policy_block(rec: dict | None) -> dict | None:
    if not rec or rec.get("status") != "ok":
        return None
    return {
        "max_people": rec.get("max_people"),
        "max_adults": rec.get("max_adults"),
        "max_children": rec.get("max_children"),
        "eligibility": rec.get("eligibility"),
        "free_under_age": rec.get("free_under_age"),
        "savings_per_person_usd": rec.get("savings_per_person_usd"),
        "notes": rec.get("notes"),
        "raw": rec.get("raw"),
    }


def build_passes(catalog: dict, policies: dict | None = None) -> dict:
    """Return {passes: [...], _meta: {...}}.

    Each element of `passes` is a (library_id, attraction_slug) row carrying
    discount, pass_type, source_url, availability calendar, and policy.

    Args:
        catalog: parsed library_catalog.json
        policies: optional dict "{lib_id}_{slug}" → parsed
                  data/raw/pass_policies/{lib_id}_{slug}.json
    """
    policies = policies or {}
    out = []
    for lib_id, lib_entry in catalog.get("libraries", {}).items():
        for slug, p in lib_entry.get("passes", {}).items():
            cal = p.get("calendar")
            policy_key = f"{lib_id}_{slug}"
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
                "policy": _policy_block(policies.get(policy_key)),
                "source_url": p.get("source_url", ""),
                "availability": cal if cal else None,
            })
    return {
        "_meta": {
            "built_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "n_passes": len(out),
            "n_with_availability": sum(1 for x in out if x["availability"]),
            "n_with_policy": sum(1 for x in out if x["policy"]),
        },
        "passes": out,
    }
