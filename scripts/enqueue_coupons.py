"""Walk all data/raw/<platform>/catalog/*.json and enqueue coupon LLM extractions.

Output: data/raw/<platform>/_pending/coupons/<lib>__<slug>.json per pass with
non-empty benefit_text.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from malibbene.sources_v2.coupons.enqueue import enqueue_coupon


def main():
    raw = ROOT / "data/raw"
    n_enqueued = 0
    n_skipped = 0
    for cat_file in raw.glob("*/catalog/*.json"):
        platform = cat_file.parts[-3]
        try:
            cat = json.loads(cat_file.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"SKIP unreadable {cat_file}: {e}")
            continue
        lib = cat.get("library_id") or cat_file.stem
        for p in cat.get("passes", []):
            slug = p.get("attraction_slug")
            if not slug:
                continue
            benefit = (p.get("benefit_text") or "").strip()
            phrases = p.get("source_phrases", []) or []
            if not benefit and not phrases:
                n_skipped += 1
                continue
            enqueue_coupon(
                library_id=lib,
                attraction_slug=slug,
                benefit_text=benefit,
                source_phrases=phrases,
                platform=platform,
                raw_root=raw,
            )
            n_enqueued += 1
    print(f"enqueued: {n_enqueued}; skipped (no benefit_text): {n_skipped}")


if __name__ == "__main__":
    main()
