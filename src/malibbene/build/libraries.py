from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, timezone
from malibbene.common.audit_overrides import load_overrides, apply_overrides

def build_libraries(seed_path: Path, raw_root: Path, overrides_root: Path, out_path: Path) -> dict:
    seeds = json.loads(seed_path.read_text())
    overrides = load_overrides(overrides_root)
    libs = []
    for s in seeds:
        lib = {
            "id": s["id"], "name": s["name"], "town": s["town"],
            "network": s["network"], "platform": s["platform"],
            "card_page": s.get("card_page"), "address": s.get("address"),
            "geo": s.get("geo"),
            "card_eligibility": "unknown",
            "pass_pickup_default": "unknown",
        }
        policies_path = raw_root / s["platform"] / "policies" / f"{s['id']}.json"
        if policies_path.exists():
            pol = json.loads(policies_path.read_text())
            if pol.get("card_page"):
                lib["card_eligibility"] = pol["card_page"].get("card_eligibility","unknown")
                lib["eligibility_source_phrase"] = pol["card_page"].get("policy_text","")[:500]
            if pol.get("pass_page"):
                lib["pass_pickup_default"] = pol["pass_page"].get("pass_pickup","unknown")
                lib["pickup_source_phrase"] = pol["pass_page"].get("policy_text","")[:500]
        lib = apply_overrides(f"library:{s['id']}", lib, overrides)
        libs.append(lib)
    out = {
        "_meta": {"built_at": datetime.now(timezone.utc).isoformat(),"n_libraries": len(libs)},
        "libraries": libs,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    return out
