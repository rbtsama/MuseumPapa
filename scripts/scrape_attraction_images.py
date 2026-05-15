"""Download og:image hero for each attraction."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from malibbene.sources.attractions.images import scrape_one


def main() -> int:
    idx_path = REPO / "data" / "structured" / "_tmp_attractions_index.json"
    if not idx_path.exists():
        print("ERROR: run scripts/build_attractions_index.py first", file=sys.stderr)
        return 1
    idx = json.loads(idx_path.read_text(encoding="utf-8"))

    meta_dir = REPO / "data" / "raw" / "attraction_images"
    img_dir = REPO / "data" / "static" / "images"
    meta_dir.mkdir(parents=True, exist_ok=True)
    img_dir.mkdir(parents=True, exist_ok=True)

    ok = 0
    total = 0
    entries = [(slug, e) for slug, e in idx.items() if not slug.startswith("_")]
    for slug, entry in entries:
        total += 1
        meta_path = meta_dir / f"{slug}.json"
        if meta_path.exists():
            existing = json.loads(meta_path.read_text(encoding="utf-8"))
            if existing.get("status") == "ok":
                ok += 1
                continue
        website = entry.get("website") or ""
        print(f"[{total}/{len(entries)}] {slug} <- {website}", flush=True)
        result = scrape_one(slug, website, out_dir=img_dir)
        meta_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        if result["status"] == "ok":
            ok += 1

    ratio = ok / total if total else 0
    print(f"Done. ok={ok}/{total} = {ratio:.1%}")
    return 0 if ratio >= 0.80 else 1


if __name__ == "__main__":
    sys.exit(main())
