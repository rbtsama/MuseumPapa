"""Read config/library_seeds.json and dispatch to sources_v2/<platform>/.

Per-library output:
  data/raw/<platform>/catalog/<lib_id>.json
  data/raw/<platform>/availability/<lib_id>/<slug>.json   (assabet/libcal)
  data/raw/<platform>/policies/<lib_id>.json
  data/raw/libcal/branches/<lib_id>.json                  (BPL/Cambridge/Brookline only)
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

def main():
    seeds = json.loads((ROOT/"config/library_seeds.json").read_text(encoding="utf-8"))
    if isinstance(seeds, dict):
        seeds = seeds["libraries"]
    raw = ROOT/"data/raw"
    summary = {"catalog_ok":0,"catalog_fail":0,"policy_ok":0,"policy_fail":0,"branches_ok":0,"errors":[]}
    catalog_dir = raw/"assabet"/"catalog"
    for s in seeds:
        _run_one(s, raw, summary)
    print(summary, flush=True)

def _run_one(seed: dict, raw: Path, summary: dict):
    lib_id = seed["id"]; platform = seed["platform"]
    if platform == "assabet":
        from malibbene.sources_v2.assabet import catalog, policies
        base = seed.get("assabet_base") or (f"https://{seed['domain']}" if seed.get("domain") else None)
        if base:
            _stage("catalog", lib_id, lambda: catalog.scrape_library(lib_id, base, raw), summary)
        if seed.get("card_page"):
            _stage("policy", lib_id, lambda: policies.scrape_policies(
                lib_id, seed["card_page"], seed.get("pass_page"), raw), summary)
    elif platform == "libcal":
        from malibbene.sources_v2.libcal import catalog, policies, branches
        libcal_base = seed.get("libcal_base") or seed.get("base_url")
        if libcal_base:
            _stage("catalog", lib_id, lambda: catalog.scrape_library(lib_id, libcal_base, raw), summary)
        if seed.get("card_page"):
            _stage("policy", lib_id, lambda: policies.scrape_policies(
                lib_id, seed["card_page"], seed.get("pass_page"), raw), summary)
        if lib_id in ("bpl","cambridge","brookline") and seed.get("locations_url"):
            _stage("branches", lib_id, lambda: branches.scrape_branches(
                lib_id, seed["locations_url"], raw), summary)
    elif platform == "museumkey":
        from malibbene.sources_v2.museumkey import catalog, policies
        base = seed.get("base_url") or seed.get("museumkey_base")
        if base:
            _stage("catalog", lib_id, lambda: catalog.scrape_library(lib_id, base, raw), summary)
        if seed.get("card_page"):
            _stage("policy", lib_id, lambda: policies.scrape_policies(
                lib_id, seed["card_page"], seed.get("pass_page"), raw), summary)

def _stage(name: str, lib_id: str, fn, summary: dict):
    try:
        fn()
        summary[f"{name}_ok"] = summary.get(f"{name}_ok", 0) + 1
        print(f"OK {name} {lib_id}", flush=True)
    except Exception as e:
        summary[f"{name}_fail"] = summary.get(f"{name}_fail", 0) + 1
        summary["errors"].append({"stage":name,"lib":lib_id,"error":str(e)})
        print(f"FAIL {name} {lib_id}: {e}", flush=True)

if __name__ == "__main__":
    main()
