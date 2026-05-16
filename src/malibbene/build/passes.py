"""Build final passes.json — flat list of (library × attraction) pass entries."""
from __future__ import annotations

import datetime as dt

# pass_type values from normalize_benefit that imply a physical pickup at the
# library branch (vs. an email-delivered digital coupon).
_PHYSICAL_PASS_TYPES = {"physical-circ", "physical-coupon"}


def _resolve_pickup(
    *,
    library_id: str,
    attraction_slug: str,
    pass_type: str,
    classifications: dict,
    branch_ids_by_lib: dict[str, list[str]],
) -> tuple[str, list[str]]:
    """Return (pickup_method, pickup_branches) for one pass.

    Priority:
      1. Subagent classification (covers BPL/Cambridge/Brookline incl. their
         empty/`unknown` pass_type cases) — takes precedence so branch-specific
         pickup_branches lists land in passes.json.
      2. Normalized pass_type from the catalog (covers Assabet + LibCal
         Braintree/Milton + MuseumKey) — single-branch lib, so physical maps to
         the synthetic `<lib_id>--main` branch.
      3. Fallback: treat as digital with empty branches.
    """
    lib_classifications = classifications.get(library_id, {})
    if attraction_slug in lib_classifications:
        entry = lib_classifications[attraction_slug]
        method = entry["pickup_method"]
        branches = entry.get("pickup_branches") or []
        return method, list(branches)

    if pass_type in _PHYSICAL_PASS_TYPES:
        ids = branch_ids_by_lib.get(library_id, [])
        if not ids:
            ids = [f"{library_id}--main"]
        return "physical_at_branch", list(ids)

    if pass_type == "digital":
        return "digital", []

    return "digital", []


def _policy_block(rec: dict | None) -> dict | None:
    if not rec or rec.get("status") != "ok":
        return None
    return {
        "max_people": rec.get("max_people"),
        "max_adults": rec.get("max_adults"),
        "max_children": rec.get("max_children"),
        "free_under_age": rec.get("free_under_age"),
        "savings_per_person_usd": rec.get("savings_per_person_usd"),
        "discount_percent": rec.get("discount_percent"),
        "discount_dollar_off": rec.get("discount_dollar_off"),
        "eligibility_tags": rec.get("eligibility_tags") or [],
        "exclusions": rec.get("exclusions") or [],
        "boosts": rec.get("boosts") or [],
        "notes": rec.get("notes"),
        "raw": rec.get("raw"),
    }


def build_passes(
    catalog: dict,
    policies: dict | None = None,
    *,
    classifications: dict | None = None,
    branches_doc: dict | None = None,
) -> dict:
    """Return {passes: [...], _meta: {...}}.

    Each element of `passes` is a (library_id, attraction_slug) row carrying
    discount, pass_type, pickup_method, pickup_branches, source_url, availability
    calendar, and policy.

    Args:
        catalog: parsed library_catalog.json
        policies: optional dict "{lib_id}_{slug}" → parsed
                  data/raw/pass_policies/{lib_id}_{slug}.json
        classifications: optional {lib_id: {pass_id: {pickup_method, pickup_branches, ...}}}
                  produced by plan-6 subagent classifiers (BPL/Cambridge/Brookline).
        branches_doc: optional structured/branches.json — used to enumerate
                  branch ids per parent_lib for the single-branch fallback.
    """
    policies = policies or {}
    classifications = classifications or {}
    branch_ids_by_lib: dict[str, list[str]] = {}
    if branches_doc:
        for b in branches_doc.get("branches", []):
            branch_ids_by_lib.setdefault(b["parent_lib_id"], []).append(b["id"])

    out = []
    n_physical = 0
    for lib_id, lib_entry in catalog.get("libraries", {}).items():
        for slug, p in lib_entry.get("passes", {}).items():
            cal = p.get("calendar")
            policy_key = f"{lib_id}_{slug}"
            pass_type = p.get("pass_type", "unknown")
            pickup_method, pickup_branches = _resolve_pickup(
                library_id=lib_id,
                attraction_slug=slug,
                pass_type=pass_type,
                classifications=classifications,
                branch_ids_by_lib=branch_ids_by_lib,
            )
            if pickup_method == "physical_at_branch":
                n_physical += 1
            out.append({
                "library_id": lib_id,
                "attraction_slug": slug,
                "pass_type": pass_type,
                "pass_type_raw": p.get("pass_type_raw", ""),
                "pickup_method": pickup_method,
                "pickup_branches": pickup_branches,
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
            "n_physical_at_branch": n_physical,
            "n_digital": len(out) - n_physical,
        },
        "passes": out,
    }
