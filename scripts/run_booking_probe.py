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

# A card is a valid non-resident prober for a target library when it is on the
# SAME network but issued by a DIFFERENT town (the operator lives in Wakefield,
# so every owned card carries a Wakefield ZIP -> genuine non-resident at every
# town except Wakefield). We hold one card per network:
#   NOBLE     -> wakefield (and reading, used to probe wakefield itself)
#   MVLC      -> wilmington
#   Minuteman -> somerville
# So we can cleanly probe every same-network town EXCEPT the issuing town of the
# only card we hold on that network (wilmington, somerville) — those stay
# untested. Within NOBLE we hold two cards, so wakefield is covered by reading.
NETWORK_CARD = {
    "NOBLE": ("WAKEFIELD_BARCODE", "wakefield"),
    "MVLC": ("WILMINGTON_BARCODE", "wilmington"),
    "Minuteman": ("SOMERVILLE_BARCODE", "somerville"),
    # MBLN (Metro Boston Library Network) = BPL + Malden + Chelsea. The BPL card
    # is MBLN; the operator's BPL card carries a Wakefield (non-Boston/Malden/
    # Chelsea) address, so it's a genuine same-network non-resident prober for
    # the MBLN assabet libraries (malden, chelsea). BPL itself is libcal and is
    # the issuing town -> can't be probed (no second MBLN card).
    "MBLN": ("BPL_BARCODE", "bpl"),
}
# Override prober for libraries that ARE the issuing town of the network card.
PROBER_OVERRIDE = {
    "wakefield": ("READING_BARCODE", "reading"),  # NOBLE, different town
    # wilmington (MVLC) and somerville (Minuteman): no second same-network card -> untested
}
UNTESTABLE = {"wilmington", "somerville"}
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


def _prober_for(lib: str, network: str):
    """Return (env_var, card_label) of a same-network non-resident card, or None."""
    if lib in UNTESTABLE:
        return None
    if lib in PROBER_OVERRIDE:
        return PROBER_OVERRIDE[lib]
    return NETWORK_CARD.get(network)


def main():
    cards = _load_env()
    seeds = {s["id"]: s for s in json.loads((ROOT / "config/library_seeds.json").read_text(encoding="utf-8"))["libraries"]}
    out_dir = ROOT / "data/raw/assabet/residency_probe"
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = {"probed": 0, "resident_only": 0, "open": 0,
               "no_conclusive_date": 0, "untested_libs": 0, "errors": 0, "booked_unexpectedly": 0}

    # Default: every Assabet library on a network we hold a card for.
    if sys.argv[1:]:
        targets = sys.argv[1:]
    else:
        targets = [s["id"] for s in seeds.values()
                   if s.get("platform") == "assabet" and s.get("network") in NETWORK_CARD]
    for lib in targets:
        network = seeds[lib].get("network")
        prober = _prober_for(lib, network)
        if not prober:
            summary["untested_libs"] += 1
            print(f"SKIP {lib} ({network}): no same-network non-resident card — residency untested")
            continue
        env_var, card_label = prober
        card = cards[env_var]
        base = f"https://{seeds[lib]['domain']}"
        cat_f = ROOT / f"data/raw/assabet/catalog/{lib}.json"
        if not cat_f.exists():
            print(f"SKIP {lib}: no catalog")
            continue
        passes = json.loads(cat_f.read_text(encoding="utf-8")).get("passes", [])
        print(f"== {lib} ({network}) via {card_label} card — {len(passes)} passes")
        for p in passes:
            slug = p["attraction_slug"]
            verdict = None
            probed_date = None
            for ym, day in _available_dates(lib, slug):
                url = _date_path(base, slug, ym, day)
                res = None
                for attempt in range(3):  # connection resets are common; retry
                    try:
                        res = probe_card(url, card)
                        break
                    except Exception as e:
                        if attempt == 2:
                            summary["errors"] += 1
                            print(f"  ! {lib}/{slug}: {type(e).__name__}: {str(e)[:50]}")
                        time.sleep(2.0 * (attempt + 1))
                if res is None:
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
                      "evidence": f"non-resident {card_label} card (same {network} network) blocked at card-validation"}
                summary["resident_only"] += 1
                tag = "RESIDENT-ONLY"
            elif verdict == "accepted":
                rr = {"restricted": "no", "scope": None,
                      "evidence": f"non-resident {card_label} card (same {network} network) accepted at card-validation (advanced to reserver-info; not booked)"}
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
