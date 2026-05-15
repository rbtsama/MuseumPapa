"""Geocode all attractions + libraries; write data/structured/geo.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from malibbene.common import geocode as gmod


def _attraction_query(entry: dict) -> str | None:
    addr = (entry.get("address") or "").strip()
    return addr or None


def _library_query(addr_record: dict) -> str | None:
    if addr_record.get("status") != "ok":
        return None
    parts = [addr_record.get("street"), addr_record.get("city"),
             addr_record.get("state"), addr_record.get("zip")]
    parts = [p for p in parts if p]
    return ", ".join(parts) if parts else None


def main() -> int:
    structured = REPO / "data" / "structured"
    idx_path = structured / "_tmp_attractions_index.json"
    if not idx_path.exists():
        print("ERROR: run scripts/build_attractions_index.py first", file=sys.stderr)
        return 1

    attractions_idx = json.loads(idx_path.read_text(encoding="utf-8"))
    libaddr_dir = REPO / "data" / "raw" / "library_addresses"

    out: dict = {"attractions": {}, "libraries": {}}

    # Attractions
    n_ok = 0
    n_attr = 0
    for slug, entry in attractions_idx.items():
        if slug.startswith("_"):
            continue  # _meta etc.
        n_attr += 1
        q = _attraction_query(entry)
        if not q:
            out["attractions"][slug] = {"ok": False, "error": "no_address"}
            continue
        r = gmod.geocode(q)
        out["attractions"][slug] = r
        if r.get("ok"):
            n_ok += 1
    print(f"Attractions: {n_ok}/{n_attr} geocoded")

    # Libraries
    n_ok = 0
    n_total = 0
    if libaddr_dir.exists():
        for f in sorted(libaddr_dir.glob("*.json")):
            if f.name.startswith("_"):
                continue  # _fetch_log.json
            n_total += 1
            rec = json.loads(f.read_text(encoding="utf-8"))
            q = _library_query(rec)
            if not q:
                out["libraries"][f.stem] = {"ok": False, "error": "no_address"}
                continue
            r = gmod.geocode(q)
            out["libraries"][f.stem] = r
            if r.get("ok"):
                n_ok += 1
    print(f"Libraries: {n_ok}/{n_total} geocoded")

    (structured / "geo.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Wrote {structured / 'geo.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
