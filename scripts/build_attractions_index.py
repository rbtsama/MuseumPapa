"""Build a temporary canonical attractions index from raw/*/index/*.json.

Output: data/structured/_tmp_attractions_index.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _load_platform_map(config_root: Path, platform: str) -> dict[str, dict[str, str]]:
    p = config_root / "platform_pass_ids" / f"{platform}.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _canonical_slug(pass_obj: dict, lib_id: str, platform: str, pmap: dict) -> str | None:
    if platform == "assabet":
        return pass_obj.get("slug")
    if platform == "libcal":
        sid = pass_obj.get("libcal_pass_id") or pass_obj.get("pass_id")
        return pmap.get(lib_id, {}).get(str(sid))
    if platform == "museumkey":
        sid = pass_obj.get("museum_id") or pass_obj.get("pass_id")
        return pmap.get(lib_id, {}).get(str(sid))
    return None


def build_index(raw_root: Path, config_root: Path | None = None) -> dict:
    if config_root is None:
        config_root = REPO / "config"

    out: dict[str, dict] = {}
    for platform in ("assabet", "libcal", "museumkey"):
        pmap = _load_platform_map(config_root, platform)
        platform_dir = raw_root / platform / "index"
        if not platform_dir.exists():
            continue
        for lib_file in sorted(platform_dir.glob("*.json")):
            lib_id = lib_file.stem
            data = json.loads(lib_file.read_text(encoding="utf-8"))
            for p in data.get("passes", []):
                if str(p.get("status", "")).startswith("failed"):
                    continue
                slug = _canonical_slug(p, lib_id, platform, pmap)
                if not slug:
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
    return out


def main() -> int:
    raw_root = REPO / "data" / "raw"
    idx = build_index(raw_root)
    out_path = REPO / "data" / "structured" / "_tmp_attractions_index.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(idx, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(idx)} attractions to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
