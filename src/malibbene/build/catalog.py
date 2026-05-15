"""Merge raw catalog + availability across platforms; normalize benefit labels.

Output is the canonical intermediate `library_catalog.json` — nested by lib_id,
with each pass keyed by canonical benefit slug. Calendar data attached when
available. `manual_overrides.json` is NOT applied here (later step).
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from malibbene.common.normalize import normalize as normalize_benefit

REPO = Path(__file__).resolve().parents[3]


def _load_platform_maps(config_root: Path) -> dict:
    bpl_raw = json.loads((config_root / "platform_pass_ids" / "bpl.json").read_text(encoding="utf-8"))
    libcal_raw = json.loads((config_root / "platform_pass_ids" / "libcal.json").read_text(encoding="utf-8"))
    mk_raw = json.loads((config_root / "platform_pass_ids" / "museumkey.json").read_text(encoding="utf-8"))

    bpl_inv = {v: k for k, v in bpl_raw.get("passes", {}).items()}

    libcal_lookup = {}
    for lib_id, info in libcal_raw.get("libraries", {}).items():
        libcal_lookup[lib_id] = info.get("passes", {})

    mk_n2b = mk_raw.get("name_to_benefit", {})
    return {
        "bpl_inverted": bpl_inv,
        "libcal_by_lib": libcal_lookup,
        "museumkey": {"name_to_benefit": mk_n2b, "canonical_set": set(mk_n2b.values())},
    }


def _canonical_slug(pass_obj: dict, lib_id: str, platform: str, maps: dict) -> str | None:
    if platform == "assabet":
        return pass_obj.get("slug")
    if platform == "libcal":
        if lib_id == "bpl":
            return maps["bpl_inverted"].get(pass_obj.get("pass_id"))
        return maps["libcal_by_lib"].get(lib_id, {}).get(pass_obj.get("slug"))
    if platform == "museumkey":
        slug = pass_obj.get("slug")
        if slug and slug in maps["museumkey"]["canonical_set"]:
            return slug
        return maps["museumkey"]["name_to_benefit"].get(
            (pass_obj.get("museum_name") or "").lower()
        )
    return None


def build_library_catalog(raw_root: Path, *, config_root: Path | None = None) -> dict:
    if config_root is None:
        config_root = REPO / "config"
    maps = _load_platform_maps(config_root)

    libs: dict[str, dict] = {}
    n_unmapped = {"assabet": 0, "libcal": 0, "museumkey": 0}
    n_passes_total = 0

    for platform in ("assabet", "libcal", "museumkey"):
        idx_dir = raw_root / platform / "index"
        avail_dir = raw_root / platform / "availability"
        if not idx_dir.exists():
            continue
        for idx_file in sorted(idx_dir.glob("*.json")):
            lib_id = idx_file.stem
            idx_data = json.loads(idx_file.read_text(encoding="utf-8"))
            avail_data = None
            avail_file = avail_dir / f"{lib_id}.json" if avail_dir.exists() else None
            if avail_file and avail_file.exists():
                avail_data = json.loads(avail_file.read_text(encoding="utf-8"))

            lib_entry = libs.setdefault(lib_id, {
                "platform": platform,
                "scraped_at": idx_data.get("scraped_at"),
                "passes": {},
            })

            for raw_pass in idx_data.get("passes", []):
                if str(raw_pass.get("status", "")).startswith("failed"):
                    continue
                slug = _canonical_slug(raw_pass, lib_id, platform, maps)
                if not slug:
                    n_unmapped[platform] += 1
                    continue
                label, label_class = normalize_benefit(raw_pass.get("benefits_text", "") or "")
                pass_entry = {
                    "museum_name": raw_pass.get("museum_name", ""),
                    "address": raw_pass.get("address", ""),
                    "website": raw_pass.get("website", ""),
                    "categories": list(raw_pass.get("categories", [])),
                    "pass_type": raw_pass.get("pass_type", "unknown"),
                    "pass_type_raw": raw_pass.get("pass_type_raw", ""),
                    "benefits_text": raw_pass.get("benefits_text", ""),
                    "benefit_label": label,
                    "benefit_class": label_class,
                    "source_url": raw_pass.get("url", ""),
                }
                if avail_data:
                    cal_entry = avail_data.get("passes", {}).get(slug) or avail_data.get("passes", {}).get(raw_pass.get("slug", ""))
                    if cal_entry and cal_entry.get("status") == "ok":
                        pass_entry["calendar"] = cal_entry.get("calendar", {})
                lib_entry["passes"][slug] = pass_entry
                n_passes_total += 1

    return {
        "_meta": {
            "built_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "n_libraries": len(libs),
            "n_passes_total": n_passes_total,
            "n_unmapped_passes_per_platform": n_unmapped,
        },
        "libraries": libs,
    }
