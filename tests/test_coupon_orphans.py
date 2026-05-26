"""Every raw coupon file with status=ok must be reachable by a pass entry.

Orphans mean the slug naming drifted between scraper and catalog (Wakefield's
"Patuxent" typo was discovered this way). Failing forces the alias to be added
to slug_canonical.LEGACY_TO_CANONICAL or the file renamed/removed.

The guard models build_passes' ACTUAL lookup: for each pass it reads
``pass_coupons/{lib}_{attraction_slug}.json`` then ``{lib}_{attraction_rawslug}.json``
(passes.py). So a file ``{lib}_{F}.json`` is reachable iff some pass for that
library has attraction_slug == F or attraction_rawslug == F. (The previous
version only compared canonical(file slug) to attraction_slug, missing the
rawslug path — and indexed p["coupon"] unguarded, crashing on null coupons.)
"""
from __future__ import annotations

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_no_orphan_raw_coupon_files():
    raw_dir = ROOT / "data" / "raw" / "pass_coupons"
    passes = json.loads((ROOT / "data" / "structured" / "passes.json").read_text(encoding="utf-8"))["passes"]

    # Every (library, slug) the build will look a coupon file up under.
    reachable: set[tuple[str, str]] = set()
    for p in passes:
        reachable.add((p["library_id"], p["attraction_slug"]))
        if p.get("attraction_rawslug"):
            reachable.add((p["library_id"], p["attraction_rawslug"]))

    orphans: list[str] = []
    for f in sorted(raw_dir.glob("*.json")):
        rec = json.loads(f.read_text(encoding="utf-8"))
        if rec.get("status") != "ok":
            continue
        lib, _, slug = f.stem.partition("_")
        if (lib, slug) not in reachable:
            orphans.append(f.name)

    assert not orphans, (
        f"{len(orphans)} raw coupon files no pass will ever read — "
        f"add the slug alias to LEGACY_TO_CANONICAL or rename/remove the file:\n  "
        + "\n  ".join(orphans[:20])
    )
