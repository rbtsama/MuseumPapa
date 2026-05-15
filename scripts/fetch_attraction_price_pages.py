"""Fetch admission/tickets page HTML for all attractions.

Writes:
- data/raw/attraction_prices/_pages/<slug>.html  (gitignored)
- data/raw/attraction_prices/_fetch_log.json     (per-attraction status)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from malibbene.sources.attractions.prices import fetch_one


def main() -> int:
    idx_path = REPO / "data" / "structured" / "_tmp_attractions_index.json"
    if not idx_path.exists():
        print("ERROR: run scripts/build_attractions_index.py first", file=sys.stderr)
        return 1
    idx = json.loads(idx_path.read_text(encoding="utf-8"))

    pages_dir = REPO / "data" / "raw" / "attraction_prices" / "_pages"
    log_path = REPO / "data" / "raw" / "attraction_prices" / "_fetch_log.json"
    pages_dir.mkdir(parents=True, exist_ok=True)

    log = {}
    ok = 0
    total = 0
    entries = [(slug, entry) for slug, entry in idx.items() if not slug.startswith("_")]
    for slug, entry in entries:
        total += 1
        # Resume support: skip if already fetched
        if (pages_dir / f"{slug}.html").exists():
            log[slug] = {"slug": slug, "status": "ok_resumed"}
            ok += 1
            continue
        website = entry.get("website") or ""
        if not website.startswith("http"):
            result = {"slug": slug, "status": "failed:no_website"}
        else:
            print(f"[{total}/{len(entries)}] {slug} <- {website}", flush=True)
            result = fetch_one(slug, website, out_dir=pages_dir)
        log[slug] = result
        if result["status"] in ("ok", "ok_resumed"):
            ok += 1

    log_path.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")
    ratio = ok / total if total else 0
    print(f"Done. ok={ok}/{total} = {ratio:.1%}")
    return 0 if ratio >= 0.80 else 1


if __name__ == "__main__":
    sys.exit(main())
