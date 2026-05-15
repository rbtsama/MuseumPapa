"""Fetch the main-site HTML page for each of 59 libraries.

Writes:
- data/raw/library_addresses/_pages/<lib_id>.html  (gitignored)
- data/raw/library_addresses/_fetch_log.json       (per-lib status summary)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import urlparse

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from malibbene.sources.libraries.addresses import fetch_one


def derive_base_url(seed: dict) -> str | None:
    """Prefer card_page (the library's own site); skip if only platform domain."""
    if seed.get("card_page"):
        p = urlparse(seed["card_page"])
        return f"{p.scheme}://{p.netloc}/"
    return None


def main() -> int:
    seeds = json.loads((REPO / "config" / "library_seeds.json").read_text(encoding="utf-8"))
    pages_dir = REPO / "data" / "raw" / "library_addresses" / "_pages"
    fetch_log_path = REPO / "data" / "raw" / "library_addresses" / "_fetch_log.json"
    pages_dir.mkdir(parents=True, exist_ok=True)

    log = {}
    ok = 0
    total = 0
    libraries = seeds["libraries"]
    for seed in libraries:
        total += 1
        base = derive_base_url(seed)
        if not base:
            result = {"lib_id": seed["id"], "status": "failed:no_base_url"}
        else:
            print(f"[{total}/{len(libraries)}] {seed['id']} <- {base}", flush=True)
            result = fetch_one(seed["id"], base, out_dir=pages_dir)
        log[seed["id"]] = result
        if result["status"] == "ok":
            ok += 1

    fetch_log_path.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")
    ratio = ok / total if total else 0
    print(f"Done. ok={ok}/{total} = {ratio:.1%}")
    return 0 if ratio >= 0.80 else 1


if __name__ == "__main__":
    sys.exit(main())
