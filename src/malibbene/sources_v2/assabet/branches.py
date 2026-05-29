"""Assabet-library branch (physical pickup-location) seeds.

The Assabet platform itself doesn't expose a per-library branch roster, so
we model multi-branch Assabet libraries with hand-curated seeds verified
against each library's own .org site. Coverage scope: only the libraries
that actually have more than one physical pickup point. Single-location
libraries don't need a row here — the matrix renders them as one column.

Each seed entry mirrors the libcal/branches output so `build/branches.py`
can iterate `data/raw/assabet/branches/*.json` with the same shape:

    { "id": "<lib_id>-<slug>",
      "library_id": "<lib_id>",
      "name": "...",
      "address": "...",
      "phone": "..." }
"""

from __future__ import annotations

import json
from pathlib import Path


# Verified 2026-05-29 against each library's own .org locations page.
SEEDS: dict[str, dict] = {
    "peabody": {
        "source": "https://peabodylibrary.org/",
        "branches": [
            {"slug": "main",  "name": "Main Library",
             "address": "82 Main Street, Peabody, MA 01960",
             "phone": "(978) 531-0100"},
            {"slug": "south", "name": "South Branch",
             "address": "78 Lynn Street, Peabody, MA 01960",
             "phone": "(978) 531-3380"},
            {"slug": "west",  "name": "West Branch",
             "address": "603 Lowell Street, Peabody, MA 01960",
             "phone": "(978) 535-3354"},
        ],
    },
    "somerville": {
        "source": "https://somervillepubliclibrary.org/library/hours-locations/",
        "branches": [
            {"slug": "main", "name": "Central Library",
             "address": "79 Highland Ave, Somerville, MA 02143",
             "phone": "(617) 623-5000"},
            {"slug": "east", "name": "East Branch",
             "address": "115 Broadway, Somerville, MA 02145",
             "phone": "(617) 623-5000 x2970"},
            {"slug": "west", "name": "West Branch",
             "address": "40 College Ave, Somerville, MA 02144",
             "phone": "(617) 623-5000 x2975"},
        ],
    },
    "quincy": {
        "source": "https://tcplquincy.org/locations",
        "branches": [
            {"slug": "main",         "name": "Main Library",
             "address": "40 Washington Street, Quincy, MA 02169",
             "phone": "(617) 376-1300"},
            {"slug": "north-quincy", "name": "North Quincy",
             "address": "381 Hancock Street, Quincy, MA 02171",
             "phone": "(617) 376-1320"},
            {"slug": "adams-shore",  "name": "Adams Shore",
             "address": "519 Sea Street, Quincy, MA 02169",
             "phone": "(617) 376-1325"},
            {"slug": "wollaston",    "name": "Wollaston",
             "address": "41 Beale Street, Quincy, MA 02171",
             "phone": "(617) 376-1330"},
        ],
    },
}


def write_all(raw_root: Path) -> dict[str, int]:
    """Emit one `data/raw/assabet/branches/<lib_id>.json` per seeded library.

    Returns a {lib_id: branch_count} report for the CLI to print.
    """
    out_dir = raw_root / "assabet" / "branches"
    out_dir.mkdir(parents=True, exist_ok=True)
    report: dict[str, int] = {}
    for lib_id, payload in SEEDS.items():
        branches = [
            {
                "id": f"{lib_id}-{b['slug']}",
                "library_id": lib_id,
                "name": b["name"],
                "address": b.get("address"),
                "phone": b.get("phone"),
            }
            for b in payload["branches"]
        ]
        out = {
            "library_id": lib_id,
            "source": payload["source"],
            "branches": branches,
        }
        (out_dir / f"{lib_id}.json").write_text(
            json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        report[lib_id] = len(branches)
    return report
