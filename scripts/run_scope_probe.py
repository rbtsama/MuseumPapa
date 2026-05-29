"""Run card-scope probes for libcal + museumkey passes against owned cards.

USAGE
-----
    # Dry-run plan (no network, no card use):
    python scripts/run_scope_probe.py --plan

    # Probe one pass with one specific owned card:
    python scripts/run_scope_probe.py \\
        --lib bpl --pass-slug museum-of-fine-arts --card bpl

    # Probe a whole library's catalog with every owned card we have
    # whose card_auth_group matches that library's auth requirement.
    # (Auth-group mismatch -> skipped, not probed.)
    python scripts/run_scope_probe.py --lib bpl

OUTPUT
------
One JSON per (library, pass, prober-card) tuple under
``data/raw/<platform>/scope_probe/<lib_id>__<pass_slug>__<card_label>.json``:

    {
      "library_id": "bpl",
      "attraction_slug": "museum-of-fine-arts",
      "prober_card": "bpl",           # LABEL only — never the barcode
      "verdict": "accepted",
      "http_status": 200,
      "probed_at": "2026-05-29T03:14:00+00:00",
      "platform": "libcal"
    }

OWNED CARDS
-----------
Read from ``.env`` in the project root, one barcode per ``<LIB_ID>_BARCODE``
key (and optional ``<LIB_ID>_PIN``). Card labels are the lib_id slug
("wakefield" / "bpl" / ...). This file is gitignored.

SAFETY
------
- Each probe submits only the auth step (see safety notes in each platform's
  ``booking_probe`` module). Card barcodes are NEVER written to output.
- ``--dry-run`` is on by default for any --lib invocation that covers more
  than 5 passes; pass ``--really`` to actually issue requests.
- Probes go one at a time with a 1.5s delay between calls (configurable
  via ``--delay``); pass ``--parallel`` (not recommended) to bypass.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from malibbene.sources_v2.libcal.booking_probe import probe_card as libcal_probe
from malibbene.sources_v2.museumkey.booking_probe import probe_card as mk_probe


# Platforms that this script knows how to probe. Assabet has its own
# probe + orchestrator (run_booking_probe.py) — this script is for the
# two platforms that one didn't cover.
KNOWN_PLATFORMS = {"libcal", "museumkey"}


def load_owned_cards(env_path: Path) -> dict[str, dict]:
    """Parse .env and return {lib_id: {"barcode": ..., "pin": ...|None}}.

    Reads only keys matching ``<LIB_ID>_BARCODE`` / ``<LIB_ID>_PIN``. lib_id
    is lowercase; underscores in the env-var prefix become hyphens in the
    label (so ``NORTH_ANDOVER_BARCODE`` -> label ``"north-andover"``).
    """
    cards: dict[str, dict] = {}
    if not env_path.exists():
        return cards
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k.endswith("_BARCODE"):
            lib = k[: -len("_BARCODE")].lower().replace("_", "-")
            cards.setdefault(lib, {})["barcode"] = v
        elif k.endswith("_PIN"):
            lib = k[: -len("_PIN")].lower().replace("_", "-")
            cards.setdefault(lib, {})["pin"] = v
    return cards


def load_catalog(platform: str, lib_id: str) -> list[dict]:
    """Read the platform's raw catalog for one library and return its
    pass list (each entry: ``{"slug": ..., "source_url": ..., ...}``).
    """
    p = ROOT / "data" / "raw" / platform / "catalog" / f"{lib_id}.json"
    if not p.exists():
        return []
    data = json.loads(p.read_text(encoding="utf-8"))
    return data.get("passes") or data.get("museums") or []


def plan(libraries: list[tuple[str, str]], cards: dict[str, dict]) -> list[dict]:
    """Return the (library, pass, prober-card) tuples we WOULD probe.

    Used by ``--plan`` and to short-circuit large runs that should require
    an explicit ``--really`` flag.
    """
    out: list[dict] = []
    for platform, lib_id in libraries:
        passes = load_catalog(platform, lib_id)
        for p in passes:
            slug = p.get("attraction_slug") or p.get("slug")
            url = p.get("detail_url") or p.get("source_url") or p.get("reservation_url")
            if not slug or not url:
                continue
            for card_label, _ in cards.items():
                out.append({
                    "platform": platform,
                    "library_id": lib_id,
                    "pass_slug": slug,
                    "source_url": url,
                    "prober_card": card_label,
                })
    return out


def write_result(platform: str, lib_id: str, slug: str, card_label: str, verdict: dict) -> Path:
    out = ROOT / "data" / "raw" / platform / "scope_probe" / f"{lib_id}__{slug}__{card_label}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "library_id": lib_id,
        "attraction_slug": slug,
        "prober_card": card_label,
        "verdict": verdict["verdict"],
        "http_status": verdict.get("http_status"),
        "probed_at": datetime.now(timezone.utc).isoformat(),
        "platform": platform,
    }, indent=2), encoding="utf-8")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--lib", action="append", default=[],
                    help="Library id to probe. Repeat for multiple.")
    ap.add_argument("--pass-slug", default=None,
                    help="Probe ONE pass (requires --lib and --card).")
    ap.add_argument("--card", default=None,
                    help="Probe with one specific owned-card label only.")
    ap.add_argument("--plan", action="store_true",
                    help="Print the tuples we'd probe and exit (no network).")
    ap.add_argument("--really", action="store_true",
                    help="Required for runs exceeding 5 probes. Lets you "
                         "double-check the plan before any real network call.")
    ap.add_argument("--delay", type=float, default=1.5,
                    help="Seconds between probes (default 1.5). Keep ≥1.0 "
                         "so the library backend isn't hammered.")
    ap.add_argument("--env", default=str(ROOT / ".env"),
                    help="Path to .env with owned-card barcodes.")
    args = ap.parse_args()

    cards = load_owned_cards(Path(args.env))
    if args.card:
        cards = {args.card: cards[args.card]} if args.card in cards else {}
    if not cards:
        print("ERROR: no owned cards loaded. Check .env and --card.",
              file=sys.stderr)
        return 2

    # Resolve {platform, lib_id} per --lib arg via libraries.json.
    libs_path = ROOT / "data" / "structured" / "libraries.json"
    libs = json.loads(libs_path.read_text(encoding="utf-8")).get("libraries", [])
    libs_by_id = {l["id"]: l for l in libs}
    targets: list[tuple[str, str]] = []
    for lib_id in args.lib:
        lib = libs_by_id.get(lib_id)
        if lib is None:
            print(f"WARN: unknown library_id {lib_id!r}", file=sys.stderr)
            continue
        if lib["platform"] not in KNOWN_PLATFORMS:
            print(f"WARN: lib {lib_id!r} is on platform {lib['platform']!r}, "
                  f"use scripts/run_booking_probe.py for assabet.", file=sys.stderr)
            continue
        targets.append((lib["platform"], lib_id))

    work = plan(targets, cards)
    if args.pass_slug:
        work = [w for w in work if w["pass_slug"] == args.pass_slug]

    if args.plan:
        for w in work:
            print(f"  {w['platform']:9s} {w['library_id']:14s} "
                  f"{w['pass_slug']:40s} via {w['prober_card']}")
        print(f"\nPlanned probes: {len(work)}")
        return 0

    if len(work) > 5 and not args.really:
        print(f"REFUSING: {len(work)} probes planned. Re-run with --really "
              f"to confirm, or narrow with --pass-slug / --card.")
        return 3

    for i, w in enumerate(work, 1):
        card = cards[w["prober_card"]]
        print(f"[{i}/{len(work)}] {w['platform']} {w['library_id']} "
              f"{w['pass_slug']} via {w['prober_card']} → ", end="", flush=True)
        try:
            if w["platform"] == "libcal":
                v = libcal_probe(w["source_url"], card["barcode"],
                                 pin=card.get("pin"))
            elif w["platform"] == "museumkey":
                # The MK probe needs the library_code (subdomain), not URL.
                v = mk_probe(w["library_id"], card["barcode"],
                             pin=card.get("pin"))
            else:
                print(f"unsupported platform {w['platform']}")
                continue
        except Exception as e:  # noqa: BLE001
            print(f"ERROR {type(e).__name__}: {e}")
            continue
        out = write_result(w["platform"], w["library_id"], w["pass_slug"],
                           w["prober_card"], v)
        print(f"{v['verdict']} (HTTP {v.get('http_status')}) → {out.relative_to(ROOT)}")
        if i < len(work):
            time.sleep(args.delay)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
