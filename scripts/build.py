"""Orchestrate the full build: raw/* → structured/{library_catalog, libraries, attractions, passes}.json.

Manual overrides from config/manual_overrides.json are applied LAST so they always win.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from malibbene.build.catalog import build_library_catalog
from malibbene.build.libraries import build_libraries
from malibbene.build.attractions import build_attractions
from malibbene.build.passes import build_passes
from malibbene.build.museum_policy import detect_free_under_age

# Local import (sibling script) — kept inside build_branches namespace so its
# logging stays attributed to that step rather than this orchestrator.
import build_branches  # noqa: E402


def _load_dir_jsons(d: Path) -> dict:
    """Load every *.json (except _* files) in d, return dict keyed by filename stem."""
    out = {}
    if not d.exists():
        return out
    for f in d.glob("*.json"):
        if f.name.startswith("_"):
            continue
        out[f.stem] = json.loads(f.read_text(encoding="utf-8"))
    return out


def _apply_overrides(data: dict, key_field: str, list_key: str, overrides: dict) -> None:
    """Mutate data[list_key] entries in place using overrides keyed by entry[key_field]."""
    if not overrides:
        return
    by_key = {x[key_field]: x for x in data.get(list_key, [])}
    for k, patch in overrides.items():
        if k in by_key:
            by_key[k].update(patch)


def _apply_pass_overrides(passes_doc: dict, overrides: dict) -> None:
    """Pass overrides are nested: {lib_id: {slug: {...}}}."""
    if not overrides:
        return
    for p in passes_doc.get("passes", []):
        lib_patches = overrides.get(p["library_id"])
        if lib_patches:
            patch = lib_patches.get(p["attraction_slug"])
            if patch:
                p.update(patch)


def main() -> int:
    raw_root = REPO / "data" / "raw"
    structured = REPO / "data" / "structured"
    config_root = REPO / "config"
    structured.mkdir(parents=True, exist_ok=True)

    # 1. library_catalog.json (intermediate)
    print("Building library_catalog.json...")
    catalog = build_library_catalog(raw_root, config_root=config_root)
    (structured / "library_catalog.json").write_text(
        json.dumps(catalog, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"  {catalog['_meta']['n_libraries']} libraries, {catalog['_meta']['n_passes_total']} passes")
    print(f"  unmapped per platform: {catalog['_meta']['n_unmapped_passes_per_platform']}")

    # Load enrichment data
    addresses = _load_dir_jsons(raw_root / "library_addresses")
    prices = _load_dir_jsons(raw_root / "attraction_prices")
    images = _load_dir_jsons(raw_root / "attraction_images")
    hours = _load_dir_jsons(raw_root / "attraction_hours")
    descriptions = _load_dir_jsons(raw_root / "attraction_descriptions")
    seeds = json.loads((config_root / "library_seeds.json").read_text(encoding="utf-8"))
    geo = json.loads((structured / "geo.json").read_text(encoding="utf-8"))
    overrides = json.loads((config_root / "manual_overrides.json").read_text(encoding="utf-8"))

    # 2. libraries.json
    print("Building libraries.json...")
    libs_doc = build_libraries(seeds, addresses, geo)
    _apply_overrides(libs_doc, "id", "libraries", overrides.get("libraries", {}))
    (structured / "libraries.json").write_text(
        json.dumps(libs_doc, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"  {libs_doc['_meta']['n_libraries']} libraries "
          f"({libs_doc['_meta']['n_with_address']} addr, {libs_doc['_meta']['n_with_geo']} geo)")

    # Load coupons up-front so we can detect museum-default free-under-N age tiers
    # and thread the result into BOTH attractions (as enrichment) and passes
    # (so redundant museum-policy rows get filtered from audience_policies).
    coupons = _load_dir_jsons(raw_root / "pass_coupons")
    free_map = detect_free_under_age(coupons)
    print(f"  detected free_under_age for {len(free_map)} attractions from coupon consensus")

    # 3. attractions.json
    print("Building attractions.json...")
    attr_doc = build_attractions(catalog, prices, images, geo, hours, descriptions,
                                  free_under_age_overrides=free_map)
    _apply_overrides(attr_doc, "slug", "attractions", overrides.get("attractions", {}))
    (structured / "attractions.json").write_text(
        json.dumps(attr_doc, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"  {attr_doc['_meta']['n_attractions']} attractions "
          f"({attr_doc['_meta']['n_with_price']} price, {attr_doc['_meta']['n_with_image']} img, "
          f"{attr_doc['_meta']['n_with_geo']} geo, {attr_doc['_meta']['n_with_hours']} hours)")

    # 3b. branches.json (plan-6) — must run before passes.json so the pass
    # builder can enumerate branch ids per multi-branch lib.
    print("Building branches.json...")
    branches_doc = build_branches.build()
    (structured / "branches.json").write_text(
        json.dumps(branches_doc, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"  {branches_doc['_meta']['n_branches']} branches "
          f"({branches_doc['_meta']['n_multi_branch_libs']} multi-branch libs)")

    # 4. passes.json
    print("Building passes.json...")
    # Subagent (plan-6, LibCal) and deterministic (plan-7, Assabet) classifications:
    # {lib_id: {pass_id: {pickup_method, pickup_branches, evidence}}}.
    # Glob auto-discovers any lib that has a _classified.json — no per-lib enum to maintain.
    classifications: dict = {}
    for cf in sorted((raw_root / "branches" / "_pickup").glob("*/_classified.json")):
        lib = cf.parent.name
        data = json.loads(cf.read_text(encoding="utf-8"))
        classifications[lib] = {p["pass_id"]: p for p in data.get("passes", [])}
    passes_doc = build_passes(
        catalog,
        coupons=coupons,
        classifications=classifications,
        branches_doc=branches_doc,
        free_under_age_overrides=free_map,
    )
    _apply_pass_overrides(passes_doc, overrides.get("passes", {}))
    (structured / "passes.json").write_text(
        json.dumps(passes_doc, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"  {passes_doc['_meta']['n_passes']} passes "
          f"({passes_doc['_meta']['n_with_availability']} with calendar, "
          f"{passes_doc['_meta']['n_with_coupon']} with coupon, "
          f"{passes_doc['_meta']['n_physical_at_branch']} physical_at_branch)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
