"""Every raw coupon file with status=ok must end up consumed by a pass entry.

Orphans mean the slug naming drifted between scraper and catalog (Wakefield's
"Patuxent" typo was discovered this way). Failing the build forces the alias
to be added to slug_canonical.LEGACY_TO_CANONICAL or the file renamed.
"""
from __future__ import annotations

import json
import pathlib

from malibbene.build.slug_canonical import canonical

ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_no_orphan_raw_coupon_files():
    raw_dir = ROOT / "data" / "raw" / "pass_coupons"
    passes = json.loads((ROOT / "data" / "structured" / "passes.json").read_text(encoding="utf-8"))["passes"]

    consumed: set[tuple[str, str]] = {
        (p["library_id"], p["attraction_slug"])
        for p in passes
        if p["coupon"]["audience_policies"] or p["coupon"]["capacity"]["n"] is not None
    }

    orphans: list[str] = []
    for f in sorted(raw_dir.glob("*.json")):
        rec = json.loads(f.read_text(encoding="utf-8"))
        if rec.get("status") != "ok":
            continue
        lib_id = rec.get("library_id") or f.stem.split("_", 1)[0]
        raw_slug = rec.get("attraction_slug") or f.stem.split("_", 1)[1]
        canon = canonical(raw_slug)
        if (lib_id, canon) not in consumed:
            orphans.append(f.name)

    assert not orphans, (
        f"{len(orphans)} raw coupon files never reached passes.json — "
        f"add the slug alias to LEGACY_TO_CANONICAL or rename the file:\n  "
        + "\n  ".join(orphans[:20])
    )
