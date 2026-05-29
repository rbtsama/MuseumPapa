"""Emit Assabet multi-branch library seeds to data/raw/assabet/branches/.

Idempotent — re-running just rewrites the same JSON. Seeds live in
`malibbene.sources_v2.assabet.branches.SEEDS` (hand-verified against each
library's own .org locations page; no live scrape needed for static
addresses).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from malibbene.sources_v2.assabet.branches import write_all


def main() -> int:
    raw_root = ROOT / "data" / "raw"
    report = write_all(raw_root)
    for lib_id, n in report.items():
        print(f"  {lib_id}: {n} branches → data/raw/assabet/branches/{lib_id}.json")
    print(f"OK · {len(report)} libraries, {sum(report.values())} branches total")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
