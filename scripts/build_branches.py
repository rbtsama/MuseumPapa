"""Compose data/structured/branches.json from:
  - data/raw/branches/<lib_id>.json (multi-branch libs, subagent-extracted)
  - data/structured/libraries.json (single-branch fallback: <lib_id>--main)

Output shape:
    {
      "_meta": {"built_at": "...", "n_branches": N},
      "branches": [
        {"id": "<lib_id>--<slug>", "name": "...", "parent_lib_id": "...",
         "address": {...}, "geo": {lat, lon}, "hours_raw": "..." | null}
      ]
    }
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

RAW = REPO / "data" / "raw" / "branches"
LIBS = REPO / "data" / "structured" / "libraries.json"
OUT = REPO / "data" / "structured" / "branches.json"


def build() -> dict:
    libs = json.loads(LIBS.read_text(encoding="utf-8"))["libraries"]
    multi: dict[str, dict] = {}
    for f in RAW.glob("*.json"):
        if f.name.startswith("_"):
            continue
        data = json.loads(f.read_text(encoding="utf-8"))
        multi[data["lib_id"]] = data

    branches: list[dict] = []
    for lib in libs:
        lid = lib["id"]
        if lid in multi:
            for b in multi[lid]["branches"]:
                if not b.get("geo"):
                    print(f"  skip {b['branch_id']}: missing geo")
                    continue
                branches.append({
                    "id": b["branch_id"],
                    "name": b["name"],
                    "parent_lib_id": lid,
                    "address": b["address"],
                    "geo": b["geo"],
                    "hours_raw": b.get("hours_raw"),
                })
        else:
            if not lib.get("address") or not lib.get("geo"):
                print(f"  skip {lid}--main: missing address or geo")
                continue
            branches.append({
                "id": f"{lid}--main",
                "name": lib["name"],
                "parent_lib_id": lid,
                "address": lib["address"],
                "geo": lib["geo"],
                "hours_raw": None,
            })

    return {
        "_meta": {
            "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "n_branches": len(branches),
            "n_multi_branch_libs": len(multi),
        },
        "branches": branches,
    }


def main() -> int:
    doc = build()
    OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {doc['_meta']['n_branches']} branches "
          f"(from {doc['_meta']['n_multi_branch_libs']} multi-branch libs + single-branch fallback)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
