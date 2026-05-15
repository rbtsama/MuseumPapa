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

    # 3. attractions.json
    print("Building attractions.json...")
    attr_doc = build_attractions(catalog, prices, images, geo, hours)
    _apply_overrides(attr_doc, "slug", "attractions", overrides.get("attractions", {}))
    (structured / "attractions.json").write_text(
        json.dumps(attr_doc, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"  {attr_doc['_meta']['n_attractions']} attractions "
          f"({attr_doc['_meta']['n_with_price']} price, {attr_doc['_meta']['n_with_image']} img, "
          f"{attr_doc['_meta']['n_with_geo']} geo, {attr_doc['_meta']['n_with_hours']} hours)")

    # 4. passes.json
    print("Building passes.json...")
    passes_doc = build_passes(catalog)
    _apply_pass_overrides(passes_doc, overrides.get("passes", {}))
    (structured / "passes.json").write_text(
        json.dumps(passes_doc, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"  {passes_doc['_meta']['n_passes']} passes "
          f"({passes_doc['_meta']['n_with_availability']} with calendar)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
