"""Run every static-data scraper in dependency order.

Order:
  1. assabet.index_page       — 52 Assabet libraries' master indices (must run first)
  2. libcal.index_page        — 5 LibCal libraries (BPL + Cambridge/Brookline/Braintree/Milton)
  3. museumkey.index_page     — 2 MuseumKey libraries (Cohasset, Hingham) — catalog only
  4. policies                  — 59 libraries' Get-a-Card pages
  5. attractions.sites         — attraction official sites (needs steps 1-3)
  6. attractions.reverse_lists — museum reverse lists (Discovery / JFK / MASS MoCA)
  7. holidays.us_federal       — 3-year US holiday calendar (no network)

Static data is intended to be refreshed once per quarter (or whenever an
index page changes). For daily availability, use ``scripts/scrape_dynamic.py``.
"""

from __future__ import annotations

import importlib
import sys
import time


STEPS = [
    ("Assabet master index",     "malibbene.sources.assabet.index_page"),
    ("LibCal pass index",        "malibbene.sources.libcal.index_page"),
    ("MuseumKey catalog",        "malibbene.sources.museumkey.index_page"),
    ("Library policies",         "malibbene.sources.policies"),
    ("Attraction official sites","malibbene.sources.attractions.sites"),
    ("Museum reverse lists",     "malibbene.sources.attractions.reverse_lists"),
    ("US federal holidays",      "malibbene.sources.holidays.us_federal"),
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
                print(f"  step returned {step_rc}", file=sys.stderr)
                rc = step_rc
        except Exception as e:
            print(f"  ERROR: {type(e).__name__}: {e}", file=sys.stderr)
            rc = 1
        print(f"  ({time.time() - t0:.1f}s)", file=sys.stderr)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
