"""Run availability scrapers (frequently re-run).

Order:
  1. assabet.availability  — 30-day calendar per (library × pass)
  2. bpl.availability      — 30-day calendar per BPL pass

Re-run whenever you want fresh availability data. Outputs:

  data/raw/assabet/availability/<lib_id>.json
  data/raw/bpl/availability.json

These are also copied to ``data/dynamic/`` at the end so downstream consumers
have a single canonical location to look (planned for v0.2).
"""

from __future__ import annotations

import importlib
import sys
import time


STEPS = [
    ("Assabet availability", "malibbene.sources.assabet.availability"),
    ("BPL availability", "malibbene.sources.bpl.availability"),
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
