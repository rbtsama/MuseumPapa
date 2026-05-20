"""Read config/library_seeds.json and dispatch to sources_v2/<platform>/.

Per-library output:
  data/raw/<platform>/catalog/<lib_id>.json
  data/raw/<platform>/availability/<lib_id>/<slug>.json   (assabet/libcal)
  data/raw/<platform>/policies/<lib_id>.json
  data/raw/libcal/branches/<lib_id>.json                  (BPL/Cambridge/Brookline only)
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def main():
    seeds = json.loads((ROOT/"config/library_seeds.json").read_text(encoding="utf-8"))
    if isinstance(seeds, dict):
        seeds = seeds["libraries"]
    raw = ROOT/"data/raw"
    summary = {"ok":0,"failed":0,"per_lib":[]}
    for s in seeds:
        try:
            _run_one(s, raw)
            summary["ok"] += 1
            print(f"OK {s['id']}")
        except Exception as e:
            summary["failed"] += 1
            summary["per_lib"].append({"lib":s["id"],"error":str(e)})
            print(f"FAIL {s['id']}: {e}")
    print(summary)

def _run_one(seed: dict, raw: Path):
    lib_id = seed["id"]; platform = seed["platform"]
    if platform == "assabet":
        from malibbene.sources_v2.assabet import catalog, policies
        base = seed.get("assabet_base") or seed.get("base_url") or f"https://{seed['id']}library.assabetinteractive.com"
        catalog.scrape_library(lib_id, base, raw)
        if seed.get("card_page"):
            policies.scrape_policies(lib_id, seed["card_page"], seed.get("pass_page"), raw)
    elif platform == "libcal":
        from malibbene.sources_v2.libcal import catalog, policies, branches
        libcal_base = seed.get("libcal_base") or seed.get("base_url")
        if not libcal_base:
            raise ValueError("libcal_base missing")
        catalog.scrape_library(lib_id, libcal_base, raw)
        if seed.get("card_page"):
            policies.scrape_policies(lib_id, seed["card_page"], seed.get("pass_page"), raw)
        if lib_id in ("bpl","cambridge","brookline") and seed.get("locations_url"):
            branches.scrape_branches(lib_id, seed["locations_url"], raw)
    elif platform == "museumkey":
        from malibbene.sources_v2.museumkey import catalog, policies
        base = seed.get("base_url") or seed.get("museumkey_base")
        if not base:
            raise ValueError("base_url missing for museumkey")
        catalog.scrape_library(lib_id, base, raw)
        if seed.get("card_page"):
            policies.scrape_policies(lib_id, seed["card_page"], seed.get("pass_page"), raw)
    else:
        raise ValueError(f"unknown platform: {platform}")

if __name__ == "__main__":
    main()
