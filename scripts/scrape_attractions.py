"""For each unique attraction slug in catalogs:
1) fetch HTML to data/raw/attractions/pages/<slug>.html
2) enqueue 4 extraction requests under _pending/<kind>/<slug>.json
"""
from __future__ import annotations
import json
from pathlib import Path
from malibbene.sources_v2.attractions.pages import fetch_attraction_page
from malibbene.sources_v2.attractions.visitor_eligibility import enqueue as enq_visitor
from malibbene.sources_v2.attractions.reservation import enqueue as enq_reserv
from malibbene.sources_v2.attractions.prices import enqueue as enq_prices
from malibbene.sources_v2.attractions.hours import enqueue as enq_hours

ROOT = Path(__file__).resolve().parent.parent

def main():
    catalogs = list((ROOT/"data/raw").glob("*/catalog/*.json"))
    seen = {}
    for f in catalogs:
        data = json.loads(f.read_text(encoding="utf-8"))
        for p in data.get("passes",[]):
            slug = p["attraction_slug"]
            seen.setdefault(slug, p.get("title") or slug)
    print(f"unique attractions: {len(seen)}")
    legacy_attr = ROOT/"data/_legacy"
    url_by_slug = {}
    if legacy_attr.exists():
        for snap in legacy_attr.iterdir():
            f = snap/"attractions.json"
            if f.exists():
                for a in json.loads(f.read_text(encoding="utf-8")).get("attractions",[]):
                    if a.get("website"):
                        url_by_slug[a["slug"]] = a["website"]
    raw = ROOT/"data/raw"
    for slug in seen:
        url = url_by_slug.get(slug)
        if not url:
            print(f"skip (no website): {slug}")
            continue
        try:
            fetch_attraction_page(slug, url, raw)
            html_path = raw/"attractions"/"pages"/f"{slug}.html"
            enq_visitor(slug, html_path, raw)
            enq_reserv(slug, html_path, raw)
            enq_prices(slug, html_path, raw)
            enq_hours(slug, html_path, raw)
            print(f"OK {slug}")
        except Exception as e:
            print(f"FAIL {slug}: {e}")

if __name__ == "__main__":
    main()
