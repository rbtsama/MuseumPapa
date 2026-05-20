"""Re-parse all data/raw/assabet/catalog/*.json using the cached index HTML.

The original scraper read benefit_text from per-pass detail pages (which only
contain a calendar). The fixed parser reads benefit_text from the index page.
This script walks existing catalog JSONs, locates the cached index HTML via
SHA1 of index_url, and rewrites each catalog with fresh benefit_text fields.
"""
from __future__ import annotations
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from malibbene.sources_v2.assabet.catalog import parse_index_html


def _cache_path(url: str, cache_dir: Path) -> Path:
    sha = hashlib.sha1(url.encode("utf-8")).hexdigest()
    return cache_dir / f"{sha}.html"


def main():
    cache_dir = ROOT / "data" / ".cache"
    catalog_dir = ROOT / "data/raw/assabet/catalog"
    n_reparsed = 0
    n_skipped = 0
    for cat_file in catalog_dir.glob("*.json"):
        cat = json.loads(cat_file.read_text(encoding="utf-8"))
        url = cat.get("index_url")
        if not url:
            n_skipped += 1
            continue
        cp = _cache_path(url, cache_dir)
        if not cp.exists():
            print(f"no cache for {cat_file.stem} ({url})")
            n_skipped += 1
            continue
        html = cp.read_text(encoding="utf-8", errors="replace")
        passes = parse_index_html(html, cat["library_id"])
        cat["passes"] = passes
        cat_file.write_text(json.dumps(cat, indent=2, ensure_ascii=False), encoding="utf-8")
        with_bt = sum(1 for p in passes if p.get("benefit_text"))
        print(f"OK {cat_file.stem}: {len(passes)} passes, {with_bt} with benefit_text")
        n_reparsed += 1
    print(f"\nre-parsed: {n_reparsed}; skipped: {n_skipped}")


if __name__ == "__main__":
    main()
