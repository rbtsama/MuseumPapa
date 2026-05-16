"""Build final passes.json — flat list of (library × attraction) pass entries."""
from __future__ import annotations

import datetime as dt

from .coupons import coupon_block, restrictions_block

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


def _resolve_pass_type(
    *,
    original_pass_type: str,
    pickup_method: str,
    benefits_text: str,
) -> str:
    """Derive pass_type when the catalog left it 'unknown'.

    LibCal + MuseumKey platforms don't expose a pass_type label, so plan-6's
    pass_type stays 'unknown' for ~23 cases. But plan-6's subagent classified
    pickup_method correctly, and raw text usually says 'return' for circ passes.
    Combine the two signals to recover a useful pass_type.
    """
    if original_pass_type and original_pass_type != "unknown":
        return original_pass_type
    if pickup_method == "digital":
        return "digital"
    if pickup_method == "physical_at_branch":
        text = (benefits_text or "").lower()
        if "return" in text or "returning" in text:
            return "physical-circ"
        return "physical-coupon"
    return original_pass_type or "unknown"


def build_passes(
    catalog: dict,
    coupons: dict | None = None,
    *,
    classifications: dict | None = None,
    branches_doc: dict | None = None,
) -> dict:
    """Return {passes: [...], _meta: {...}}.

    Each element of `passes` is a (library_id, attraction_slug) row carrying
    coupon, restrictions, pass_type, pickup_method, pickup_branches, source_url,
    and availability calendar.

    Args:
        catalog: parsed library_catalog.json
        coupons: optional dict "{lib_id}_{slug}" → parsed
                 data/raw/pass_coupons/{lib_id}_{slug}.json
        classifications: optional {lib_id: {pass_id: {pickup_method, pickup_branches, ...}}}
                  produced by plan-6 subagent classifiers (BPL/Cambridge/Brookline).
        branches_doc: optional structured/branches.json — used to enumerate
                  branch ids per parent_lib for the single-branch fallback.
    """
    coupons = coupons or {}
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
            coupon_key = f"{lib_id}_{slug}"
            coupon_rec = coupons.get(coupon_key)
            pass_type = p.get("pass_type", "unknown")
            pickup_method, pickup_branches = _resolve_pickup(
                library_id=lib_id,
                attraction_slug=slug,
                pass_type=pass_type,
                classifications=classifications,
                branch_ids_by_lib=branch_ids_by_lib,
            )
            pass_type = _resolve_pass_type(
                original_pass_type=pass_type,
                pickup_method=pickup_method,
                benefits_text=p.get("benefits_text", ""),
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
                "coupon": coupon_block(coupon_rec),
                "restrictions": restrictions_block(coupon_rec),
                "source_url": p.get("source_url", ""),
                "availability": cal if cal else None,
            })
    return {
        "_meta": {
            "built_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "n_passes": len(out),
            "n_with_availability": sum(1 for x in out if x["availability"]),
            "n_with_coupon": sum(1 for x in out if x["coupon"]["audience_policies"]),
            "n_with_restrictions": sum(1 for x in out if x["restrictions"] is not None),
            "n_physical_at_branch": n_physical,
            "n_digital": len(out) - n_physical,
        },
        "passes": out,
    }
