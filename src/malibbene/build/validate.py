from __future__ import annotations
import json
from pathlib import Path
from collections import Counter

def _pct(n,total): return round(100.0*n/total,1) if total else 0.0


def _referential_integrity(libs, attrs, passes) -> None:
    """Raise ValueError on structural corruption: a pass pointing at a
    library_id or attraction_slug that does not exist, or a duplicate
    (library_id, attraction_slug) pair. These are never acceptable to ship —
    slug_canonical passes unknown slugs through unchanged, so a typo or new
    platform would otherwise create a silent orphan row."""
    lib_ids = {l.get("id") for l in libs}
    attr_slugs = {a.get("slug") for a in attrs}
    orphan_lib = sorted({p.get("library_id") for p in passes if p.get("library_id") not in lib_ids})
    orphan_attr = sorted({p.get("attraction_slug") for p in passes if p.get("attraction_slug") not in attr_slugs})
    pairs = Counter((p.get("library_id"), p.get("attraction_slug")) for p in passes)
    dup_pairs = sorted(k for k, n in pairs.items() if n > 1)
    problems = []
    if orphan_lib:
        problems.append(f"{len(orphan_lib)} pass(es) reference an unknown library: {orphan_lib[:8]}")
    if orphan_attr:
        problems.append(f"{len(orphan_attr)} pass(es) reference an unknown attraction: {orphan_attr[:8]}")
    if dup_pairs:
        problems.append(f"{len(dup_pairs)} duplicate (library, attraction) pair(s): {dup_pairs[:8]}")
    if problems:
        raise ValueError("referential integrity failed:\n  " + "\n  ".join(problems))


def _duplicate_audience_count(passes) -> int:
    """Passes whose coupon lists the same (audience, age_range) more than once.
    A data-quality smell (e.g. paid Child + free-infant Child sharing a key) —
    reported, not fatal."""
    n = 0
    for p in passes:
        aps = (p.get("coupon") or {}).get("audience_policies") or []
        keys = [(a.get("audience"), json.dumps(a.get("age_range"), sort_keys=True)) for a in aps]
        if len(keys) != len(set(keys)):
            n += 1
    return n


def validate_build(libraries: Path, attractions: Path, passes_file: Path) -> dict:
    libs = json.loads(libraries.read_text())["libraries"]
    attrs = json.loads(attractions.read_text())["attractions"]
    passes = json.loads(passes_file.read_text())["passes"]

    # Hard gate: corruption must never ship.
    _referential_integrity(libs, attrs, passes)

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
            # Data-quality (non-fatal): attractions that ended up with no category
            # filter out of every category browse.
            "empty_categories_count":
                sum(1 for a in attrs if not (a.get("categories") or [])),
        },
        "passes": {
            "n": len(passes),
            "coupon_missing_pct": _pct(
                sum(1 for p in passes if not p.get("coupon")), len(passes)),
            "duplicate_audience_count": _duplicate_audience_count(passes),
        },
    }
