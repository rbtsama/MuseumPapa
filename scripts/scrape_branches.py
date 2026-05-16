"""Snapshot locations pages (default) or harvest per-pass pickup hint text (--pickup).

Usage:
    python scripts/scrape_branches.py            # fetch locations pages for 3 libs
    python scripts/scrape_branches.py --pickup   # fetch pass detail pages and slice pickup text
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from malibbene.sources.branches.locations_page import fetch_all


def main() -> None:
    if "--pickup" in sys.argv:
        from malibbene.sources.branches.pickup_hints import harvest
        for r in harvest():
            print(r)
    else:
        for r in fetch_all():
            print(r)


if __name__ == "__main__":
    main()
