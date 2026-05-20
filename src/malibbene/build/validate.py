from __future__ import annotations
import json
from pathlib import Path

def _pct(n,total): return round(100.0*n/total,1) if total else 0.0

def validate_build(libraries: Path, attractions: Path, passes_file: Path) -> dict:
    libs = json.loads(libraries.read_text())["libraries"]
    attrs = json.loads(attractions.read_text())["attractions"]
    passes = json.loads(passes_file.read_text())["passes"]
    return {
        "libraries": {
            "n": len(libs),
            "card_eligibility_unknown_pct": _pct(
                sum(1 for l in libs if l.get("card_eligibility")=="unknown"), len(libs)),
            "pass_pickup_unknown_pct": _pct(
                sum(1 for l in libs if l.get("pass_pickup_default")=="unknown"), len(libs)),
        },
        "attractions": {
            "n": len(attrs),
            "visitor_eligibility_missing_pct": _pct(
                sum(1 for a in attrs if not a.get("visitor_eligibility")), len(attrs)),
            "reservation_missing_pct": _pct(
                sum(1 for a in attrs if not a.get("reservation")), len(attrs)),
        },
        "passes": {
            "n": len(passes),
            "coupon_missing_pct": _pct(
                sum(1 for p in passes if not p.get("coupon")), len(passes)),
        },
    }
