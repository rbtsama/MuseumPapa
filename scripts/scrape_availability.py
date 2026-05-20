"""Scrape calendar availability for every pass in every Assabet + LibCal catalog.

Walks ``data/raw/<platform>/catalog/*.json`` and, for each pass entry, calls the
matching platform-specific ``scrape_availability`` from
``malibbene.sources_v2``. Museumkey is skipped — its calendar lives behind a
member-only login and is not part of v0.1 scope.

Per-pass JSON output lands at ``data/raw/<platform>/availability/<lib>/<slug>.json``
(same layout ``malibbene.build.passes`` already reads from).

Resilience rules:
- One failing pass MUST NOT abort the run. Every per-pass call is wrapped in
  try/except; failures are recorded and printed with ``FAIL ...: <reason>``.
- Progress is flushed per pass so a backgrounded run can be tailed.
- A final summary is written to ``data/raw/_scrape_availability_summary.json``
  (counts + first 10 failures with reason).
"""
from __future__ import annotations

import json
import sys
import time
import traceback
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from malibbene.sources_v2.assabet.availability import (  # noqa: E402
    scrape_availability as scrape_assabet,
)
from malibbene.sources_v2.libcal.availability import (  # noqa: E402
    scrape_availability as scrape_libcal,
)

RAW_ROOT = ROOT / "data" / "raw"
SEEDS = ROOT / "config" / "library_seeds.json"
SUMMARY_PATH = RAW_ROOT / "_scrape_availability_summary.json"


def _load_libcal_subdomains() -> dict[str, str]:
    """Map lib_id -> libcal subdomain (e.g. bpl -> 'bpl', braintree -> 'thayerpubliclibrary')."""
    libs = json.loads(SEEDS.read_text(encoding="utf-8"))["libraries"]
    out: dict[str, str] = {}
    for l in libs:
        if l.get("platform") != "libcal":
            continue
        domain = l.get("domain") or ""
        # 'bpl.libcal.com' -> 'bpl'
        sub = domain.split(".libcal.com")[0] if ".libcal.com" in domain else None
        if sub:
            out[l["id"]] = sub
    return out


def _iter_catalogs(platform: str):
    cdir = RAW_ROOT / platform / "catalog"
    if not cdir.exists():
        return
    for f in sorted(cdir.glob("*.json")):
        yield json.loads(f.read_text(encoding="utf-8"))


def _print(msg: str) -> None:
    print(msg, flush=True)


def run() -> dict:
    start = time.time()
    libcal_subs = _load_libcal_subdomains()
    today = date.today().isoformat()

    summary = {
        "started_at": today,
        "assabet_ok": 0,
        "assabet_fail": 0,
        "libcal_ok": 0,
        "libcal_fail": 0,
        "museumkey_skipped": 0,
        "total_days_scraped": 0,
        "failures": [],  # [{platform, lib, slug, reason}]
    }

    # --- Assabet ---
    for cat in _iter_catalogs("assabet"):
        lib = cat["library_id"]
        for p in cat.get("passes", []):
            slug = p.get("attraction_slug")
            url = p.get("detail_url")
            if not slug or not url:
                summary["assabet_fail"] += 1
                summary["failures"].append(
                    {"platform": "assabet", "lib": lib, "slug": slug, "reason": "missing slug or detail_url"}
                )
                _print(f"FAIL assabet {lib}/{slug}: missing slug or detail_url")
                continue
            try:
                r = scrape_assabet(lib, url, RAW_ROOT, slug)
                summary["assabet_ok"] += 1
                summary["total_days_scraped"] += r["n_days"]
                _print(f"OK   assabet {lib}/{slug} n_days={r['n_days']}")
            except Exception as e:
                reason = f"{type(e).__name__}: {e}"
                summary["assabet_fail"] += 1
                summary["failures"].append(
                    {"platform": "assabet", "lib": lib, "slug": slug, "reason": reason}
                )
                _print(f"FAIL assabet {lib}/{slug}: {reason}")

    # --- LibCal ---
    for cat in _iter_catalogs("libcal"):
        lib = cat["library_id"]
        sub = libcal_subs.get(lib)
        if not sub:
            for p in cat.get("passes", []):
                summary["libcal_fail"] += 1
                summary["failures"].append(
                    {
                        "platform": "libcal",
                        "lib": lib,
                        "slug": p.get("attraction_slug"),
                        "reason": f"no libcal subdomain for lib {lib}",
                    }
                )
                _print(f"FAIL libcal {lib}/{p.get('attraction_slug')}: no libcal subdomain")
            continue
        for p in cat.get("passes", []):
            slug = p.get("attraction_slug")
            # Prefer the 12-hex internal id (catalog extracts via JS-var scan).
            # Some libs (BPL/Braintree/Milton) already use it in the URL; others
            # (Brookline=short code, Cambridge=kebab slug) need the
            # libcal_museum_id field that the catalog parser fills in.
            pid = p.get("libcal_museum_id") or p.get("libcal_pass_id")
            if not slug or not pid:
                summary["libcal_fail"] += 1
                summary["failures"].append(
                    {"platform": "libcal", "lib": lib, "slug": slug, "reason": "missing slug or libcal_pass_id"}
                )
                _print(f"FAIL libcal {lib}/{slug}: missing slug or libcal_pass_id")
                continue
            try:
                r = scrape_libcal(lib, sub, pid, slug, today, RAW_ROOT)
                summary["libcal_ok"] += 1
                summary["total_days_scraped"] += r["n_days"]
                _print(f"OK   libcal  {lib}/{slug} n_days={r['n_days']}")
            except Exception as e:
                reason = f"{type(e).__name__}: {e}"
                summary["libcal_fail"] += 1
                summary["failures"].append(
                    {"platform": "libcal", "lib": lib, "slug": slug, "reason": reason}
                )
                _print(f"FAIL libcal  {lib}/{slug}: {reason}")

    # --- museumkey (skipped — needs login) ---
    for cat in _iter_catalogs("museumkey"):
        summary["museumkey_skipped"] += len(cat.get("passes", []))

    summary["elapsed_seconds"] = round(time.time() - start, 1)
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    _print("")
    _print(f"=== DONE in {summary['elapsed_seconds']}s ===")
    _print(
        f"assabet ok={summary['assabet_ok']} fail={summary['assabet_fail']}  "
        f"libcal ok={summary['libcal_ok']} fail={summary['libcal_fail']}  "
        f"museumkey_skipped={summary['museumkey_skipped']}  "
        f"total_days={summary['total_days_scraped']}"
    )
    return summary


if __name__ == "__main__":
    try:
        run()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
