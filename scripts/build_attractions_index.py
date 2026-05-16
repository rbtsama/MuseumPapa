"""Build a temporary canonical attractions index from raw/*/index/*.json.

Output: data/structured/_tmp_attractions_index.json
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _load_platform_map(config_root: Path, platform: str) -> dict:
    """Return a normalized lookup dict for each platform.

    bpl       -> {"_inverted_passes": {hex_pass_id: canonical_slug}}
    libcal    -> {<lib_id>: {libcal_side_slug: canonical_slug}}
    museumkey -> {"name_to_benefit": {lower_name: canonical},
                   "canonical_set": set(canonical_slugs)}
    """
    p = config_root / "platform_pass_ids" / f"{platform}.json"
    if not p.exists():
        return {}
    raw = json.loads(p.read_text(encoding="utf-8"))

    if platform == "bpl":
        passes = raw.get("passes", {})
        return {"_inverted_passes": {v: k for k, v in passes.items()}}

    if platform == "libcal":
        out: dict[str, dict[str, str]] = {}
        for lib_id, lib_cfg in (raw.get("libraries") or {}).items():
            out[lib_id] = dict(lib_cfg.get("passes") or {})
        return out

    if platform == "museumkey":
        n2b = {k.lower(): v for k, v in (raw.get("name_to_benefit") or {}).items()}
        return {
            "name_to_benefit": n2b,
            "canonical_set": set(n2b.values()),
        }

    return {}


def _canonical_slug(
    pass_obj: dict,
    lib_id: str,
    platform: str,
    pmap: dict,
    bpl_map: dict | None = None,
) -> str | None:
    """Resolve a raw pass record to its canonical attraction slug.

    Returns None if the lookup fails (caller should skip the pass).
    """
    if platform == "assabet":
        return pass_obj.get("slug")

    if platform == "libcal":
        if lib_id == "bpl":
            # BPL uses the dedicated bpl.json map (inverted: pass_id -> canonical).
            if not bpl_map:
                return None
            return bpl_map.get("_inverted_passes", {}).get(pass_obj.get("pass_id"))
        # Other libcal libs: try pass_id first (canonical key), fall back to slug.
        # Matches the fix in build/catalog.py — libcal pass_ids vary in style
        # (hex codes, short codes, slug-style) and were keyed inconsistently.
        lib_map = pmap.get(lib_id, {})
        return lib_map.get(pass_obj.get("pass_id")) or lib_map.get(pass_obj.get("slug"))

    if platform == "museumkey":
        n2b = pmap.get("name_to_benefit", {})
        canonical_set = pmap.get("canonical_set", set())
        slug = pass_obj.get("slug")
        if slug and slug in canonical_set:
            return slug
        name = pass_obj.get("museum_name") or ""
        if name:
            return n2b.get(name.lower())
        return None

    return None


def build_index(raw_root: Path, config_root: Path | None = None) -> dict:
    if config_root is None:
        config_root = REPO / "config"

    # Pre-load platform maps.
    bpl_map = _load_platform_map(config_root, "bpl")
    libcal_map = _load_platform_map(config_root, "libcal")
    museumkey_map = _load_platform_map(config_root, "museumkey")

    platform_maps = {
        "assabet": {},
        "libcal": libcal_map,
        "museumkey": museumkey_map,
    }

    out: dict[str, dict] = {}
    unmapped = {"assabet": 0, "libcal": 0, "museumkey": 0}
    n_libs_scanned = 0
    for platform in ("assabet", "libcal", "museumkey"):
        pmap = platform_maps[platform]
        platform_dir = raw_root / platform / "index"
        if not platform_dir.exists():
            continue
        for lib_file in sorted(platform_dir.glob("*.json")):
            lib_id = lib_file.stem
            n_libs_scanned += 1
            data = json.loads(lib_file.read_text(encoding="utf-8"))
            for p in data.get("passes", []):
                if str(p.get("status", "")).startswith("failed"):
                    continue
                slug = _canonical_slug(p, lib_id, platform, pmap, bpl_map=bpl_map)
                if not slug:
                    unmapped[platform] += 1
                    continue
                entry = out.setdefault(slug, {
                    "slug": slug,
                    "museum_name": p.get("museum_name", ""),
                    "address": p.get("address", ""),
                    "website": p.get("website", ""),
                    "categories": list(p.get("categories", [])),
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
    out["_meta"] = {
        "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "n_attractions": len(out),
        "n_libraries_scanned": n_libs_scanned,
        "unmapped_passes_per_platform": unmapped,
    }
    return out


def main() -> int:
    raw_root = REPO / "data" / "raw"
    idx = build_index(raw_root)
    out_path = REPO / "data" / "structured" / "_tmp_attractions_index.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(idx, indent=2, ensure_ascii=False), encoding="utf-8")
    n_attractions = sum(1 for k in idx if not k.startswith("_"))
    print(f"Wrote {n_attractions} attractions to {out_path}")
    unmapped = idx.get("_meta", {}).get("unmapped_passes_per_platform", {})
    for platform, n in unmapped.items():
        if n > 0:
            print(f"WARNING: {n} {platform} passes had no canonical mapping", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
