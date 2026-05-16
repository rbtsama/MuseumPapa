"""For Assabet multi-branch libs only: generate _classified.json deterministically.

Why no subagent: Assabet pass detail pages only expose `pass_type_raw` (digital
vs "picked up from the branch") and never name a specific branch. So the
classification is purely a function of pass_type:
  - digital  -> pickup_method=digital, pickup_branches=[]
  - physical -> pickup_method=physical_at_branch, pickup_branches=all branches of that lib

Reads:
  data/raw/branches/<lib_id>.json
  data/structured/library_catalog.json
Writes:
  data/raw/branches/_pickup/<lib_id>/_classified.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RAW = REPO / "data" / "raw" / "branches"
CAT = REPO / "data" / "structured" / "library_catalog.json"
SEEDS = REPO / "config" / "branch_seeds.json"

PHYSICAL_PASS_TYPES = {"physical-circ", "physical-coupon"}
# LibCal libs already have subagent-produced _classified.json (plan-6); don't
# overwrite those with deterministic fallback.
LIBCAL_MULTI = {"bpl", "cambridge", "brookline"}


def main() -> int:
    catalog = json.loads(CAT.read_text(encoding="utf-8"))["libraries"]
    seeds = json.loads(SEEDS.read_text(encoding="utf-8"))["multi_branch_libs"]
    multi_lib_ids = [s["lib_id"] for s in seeds if s["lib_id"] not in LIBCAL_MULTI]

    for lib_id in multi_lib_ids:
        bpath = RAW / f"{lib_id}.json"
        if not bpath.exists():
            print(f"skip {lib_id}: no branches file")
            continue
        branches = json.loads(bpath.read_text(encoding="utf-8"))["branches"]
        branch_ids = [b["branch_id"] for b in branches if b.get("geo")]
        if not branch_ids:
            print(f"skip {lib_id}: no geocoded branches")
            continue

        lib_passes = catalog.get(lib_id, {}).get("passes", {})
        out_passes = []
        for slug, p in lib_passes.items():
            pass_type = p.get("pass_type", "unknown")
            if pass_type in PHYSICAL_PASS_TYPES:
                out_passes.append({
                    "pass_id": slug,
                    "pickup_method": "physical_at_branch",
                    "pickup_branches": list(branch_ids),
                    "evidence": f"assabet_pass_type={pass_type}; default_all_branches (Assabet UI does not surface per-branch holdings)",
                })
            elif pass_type == "digital":
                out_passes.append({
                    "pass_id": slug,
                    "pickup_method": "digital",
                    "pickup_branches": [],
                    "evidence": "assabet_pass_type=digital",
                })
            else:
                out_passes.append({
                    "pass_id": slug,
                    "pickup_method": "digital",
                    "pickup_branches": [],
                    "evidence": f"assabet_pass_type={pass_type}; defaulted_digital",
                })

        outdir = RAW / "_pickup" / lib_id
        outdir.mkdir(parents=True, exist_ok=True)
        (outdir / "_classified.json").write_text(
            json.dumps({"lib_id": lib_id, "passes": out_passes}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        n_phys = sum(1 for p in out_passes if p["pickup_method"] == "physical_at_branch")
        print(f"OK {lib_id}: {len(out_passes)} passes ({n_phys} physical) × {len(branch_ids)} branches")

    return 0


if __name__ == "__main__":
    sys.exit(main())
