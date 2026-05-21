"""Empirical residency probe using the operator's own library cards.

Determines which Assabet passes are "Resident Only" by attempting the first
(card-validation) step of a reservation with a CROSS-TOWN, SAME-NETWORK card —
i.e. a card that is a genuine non-resident of the target library but is still
recognized by its network.

WHY cross-town same-network (not the local card):
- The operator's *Reading* card is a Reading patron card, so it can't reveal
  Reading's resident-only restriction. To test it we need a card that the
  Reading site recognizes (same NOBLE network) but that belongs to a
  non-Reading resident — the operator's *Wakefield* card (also NOBLE).
- Verified empirically that a Wakefield NOBLE card IS accepted at Reading
  passes, so cross-town reservation works within NOBLE; a rejection therefore
  means resident-only, not "card not on this network".

Clean probes possible with the 5 owned cards (Wakefield/Reading NOBLE,
Wilmington MVLC, Somerville Minuteman, BPL libcal):
  - reading  passes  <- wakefield card (non-Reading NOBLE resident)
  - wakefield passes <- reading card   (non-Wakefield NOBLE resident)
Wilmington / Somerville / BPL CANNOT be residency-tested here: the operator
holds only the one local card on each of those networks, so there is no
same-network non-resident card to probe with. Those are left UNKNOWN (honest).

SAFETY: only the card-validation step is submitted; the booking is never
finalized. PRIVACY: barcodes are read from .env, never printed or written.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from malibbene.sources_v2.assabet.booking_probe import probe_card, _date_path

# target library -> (env var of a same-network NON-resident card, that card's label)
CROSS_PROBE = {
    "reading":  ("WAKEFIELD_BARCODE", "wakefield"),
    "wakefield": ("READING_BARCODE", "reading"),
}
_ENV = None
_MONTHS = ["january", "february", "march", "april", "may", "june", "july",
           "august", "september", "october", "november", "december"]


def _load_env():
    global _ENV
    if _ENV is None:
        _ENV = {}
        for line in (ROOT / ".env").read_text(encoding="utf-8", errors="replace").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                _ENV[k.strip()] = v.strip().strip('"').strip("'")
    return _ENV


def _available_dates(lib: str, slug: str, limit: int = 4):
    """Yield up to `limit` (year_month, day) future available dates for retries
    (the chosen date can go stale between scrape and probe)."""
    f = ROOT / "data/raw/assabet/availability" / lib / f"{slug}.json"
    if not f.exists():
        return
    today = time.strftime("%Y-%m-%d")
    n = 0
    for d in json.loads(f.read_text(encoding="utf-8")).get("days", []):
        if d.get("status") == "available" and d.get("date", "") >= today:
            y, m, day = d["date"].split("-")
            yield f"{y}-{_MONTHS[int(m)-1]}", day
            n += 1
            if n >= limit:
                return


def main():
    cards = _load_env()
    seeds = {s["id"]: s for s in json.loads((ROOT / "config/library_seeds.json").read_text(encoding="utf-8"))["libraries"]}
    out_dir = ROOT / "data/raw/assabet/residency_probe"
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = {"probed": 0, "resident_only": 0, "open": 0,
               "no_conclusive_date": 0, "errors": 0, "booked_unexpectedly": 0}

    targets = sys.argv[1:] or list(CROSS_PROBE)
    for lib in targets:
        if lib not in CROSS_PROBE:
            print(f"SKIP {lib}: no same-network non-resident card available — residency untested")
            continue
        env_var, card_label = CROSS_PROBE[lib]
        card = cards[env_var]
        base = f"https://{seeds[lib]['domain']}"
        passes = json.loads((ROOT / f"data/raw/assabet/catalog/{lib}.json").read_text(encoding="utf-8")).get("passes", [])
        for p in passes:
            slug = p["attraction_slug"]
            verdict = None
            probed_date = None
            for ym, day in _available_dates(lib, slug):
                url = _date_path(base, slug, ym, day)
                try:
                    res = probe_card(url, card)
                except Exception as e:
                    summary["errors"] += 1
                    print(f"  ! {lib}/{slug}: {type(e).__name__}: {str(e)[:50]}")
                    time.sleep(1.0)
                    continue
                v = res["verdict"]
                if v == "booked_unexpectedly":
                    print(f"  STOP {lib}/{slug}: looked finalized — aborting")
                    summary["booked_unexpectedly"] += 1
                    return
                if v in ("accepted", "rejected_resident"):
                    verdict, probed_date = v, f"{ym}/{day}"
                    break  # conclusive
                # "unknown" (stale date) / "format_error" -> try next date
                time.sleep(0.8)
            if verdict == "rejected_resident":
                rr = {"restricted": "yes", "scope": "town",
                      "evidence": f"non-resident {card_label} card (same NOBLE network) blocked at card-validation"}
                summary["resident_only"] += 1
                tag = "RESIDENT-ONLY"
            elif verdict == "accepted":
                rr = {"restricted": "no", "scope": None,
                      "evidence": f"non-resident {card_label} card (same NOBLE network) accepted at card-validation (advanced to reserver-info; not booked)"}
                summary["open"] += 1
                tag = "open"
            else:
                summary["no_conclusive_date"] += 1
                print(f"  - {lib}/{slug}: no conclusive available date")
                continue
            summary["probed"] += 1
            out = {"library_id": lib, "attraction_slug": slug,
                   "prober_card": card_label, "probed_date": probed_date,
                   "verdict": verdict, **rr, "source": "booking_probe"}
            (out_dir / f"{lib}__{slug}.json").write_text(
                json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"  {lib}/{slug}: {tag}")
            time.sleep(1.0)

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
