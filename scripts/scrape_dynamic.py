"""Run availability scrapers (frequently re-run).

Order:
  1. assabet.availability  — 52 libraries × ~20 passes each
  2. libcal.availability   — 5 libraries (BPL + Cambridge/Brookline/Braintree/Milton)

MuseumKey (Cohasset, Hingham) is intentionally not here — its calendar
requires login (library card barcode) and is documented in BRD §A.3 as
catalog-only.

Re-run whenever you want fresh availability data. Outputs:

  data/raw/assabet/availability/<lib_id>.json
  data/raw/libcal/availability/<lib_id>.json

These are also copied to ``data/dynamic/`` at the end so downstream consumers
have a single canonical location to look (planned for v0.2).
"""

from __future__ import annotations

import importlib
import sys
import time


STEPS = [
    ("Assabet availability", "malibbene.sources.assabet.availability"),
    ("LibCal availability",  "malibbene.sources.libcal.availability"),
]


def main() -> int:
    rc = 0
    for label, module_name in STEPS:
        print(f"\n=== {label} ({module_name}) ===", file=sys.stderr)
        t0 = time.time()
        try:
            mod = importlib.import_module(module_name)
            step_rc = mod.main()
            if step_rc and step_rc != 0:
                rc = step_rc
        except Exception as e:
            print(f"  ERROR: {type(e).__name__}: {e}", file=sys.stderr)
            rc = 1
        print(f"  ({time.time() - t0:.1f}s)", file=sys.stderr)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
