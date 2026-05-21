from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, timezone
from malibbene.common.audit_overrides import load_overrides, apply_overrides

def _read_json(p): return json.loads(p.read_text()) if p.exists() else None


def _catalog_titles(raw_root: Path) -> dict:
    """slug -> best museum name from the library catalogs.

    Attraction homepages don't always expose a clean <title>/og:title, so a
    page meta title can be null. The library pass catalogs always carry a
    human name for the museum, so we use them as a fallback for the attraction
    display name. Prefer a title that has mixed case and the most words.
    """
    best: dict[str, str] = {}
    for cat_f in raw_root.glob("*/catalog/*.json"):
        try:
            cat = json.loads(cat_f.read_text(encoding="utf-8"))
        except Exception:
            continue
        for p in cat.get("passes", []):
            slug = p.get("attraction_slug")
            title = (p.get("title") or "").strip()
            if not slug or not title:
                continue
            cur = best.get(slug)
            # Prefer the longer / more descriptive title.
            if cur is None or len(title) > len(cur):
                best[slug] = title
    return best


def build_attractions(raw_root: Path, overrides_root: Path, out_path: Path) -> dict:
    pages_dir = raw_root / "attractions" / "pages"
    overrides = load_overrides(overrides_root)
    catalog_names = _catalog_titles(raw_root)
    attractions = []
    if pages_dir.exists():
        for meta_f in pages_dir.glob("*.meta.json"):
            meta = json.loads(meta_f.read_text())
            slug = meta["slug"]
            name = meta.get("title") or catalog_names.get(slug)
            a = {
                "slug": slug, "name": name,
                "website": meta.get("url"), "hero_image": meta.get("og_image"),
                "prices": [], "categories": [], "sources": [meta.get("url")],
            }
            prices = _read_json(raw_root/"attractions/prices"/f"{slug}.json")
            if prices and prices.get("status")=="ok":
                a["prices"] = prices["extracted"].get("prices",[])
            ve = _read_json(raw_root/"attractions/visitor_eligibility"/f"{slug}.json")
            if ve and ve.get("status")=="ok":
                a["visitor_eligibility"] = ve["extracted"]
            rv = _read_json(raw_root/"attractions/reservation"/f"{slug}.json")
            if rv and rv.get("status")=="ok":
                a["reservation"] = rv["extracted"]
            hr = _read_json(raw_root/"attractions/hours"/f"{slug}.json")
            if hr and hr.get("status")=="ok":
                a["hours"] = hr["extracted"].get("hours")
            a = apply_overrides(f"attraction:{slug}", a, overrides)
            attractions.append(a)
    out = {"_meta":{"built_at":datetime.now(timezone.utc).isoformat(),
                    "n_attractions":len(attractions)},
           "attractions": attractions}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    return out
