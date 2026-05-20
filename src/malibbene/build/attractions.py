from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, timezone
from malibbene.common.audit_overrides import load_overrides, apply_overrides

def _read_json(p): return json.loads(p.read_text()) if p.exists() else None

def build_attractions(raw_root: Path, overrides_root: Path, out_path: Path) -> dict:
    pages_dir = raw_root / "attractions" / "pages"
    overrides = load_overrides(overrides_root)
    attractions = []
    if pages_dir.exists():
        for meta_f in pages_dir.glob("*.meta.json"):
            meta = json.loads(meta_f.read_text())
            slug = meta["slug"]
            a = {
                "slug": slug, "name": meta.get("title"),
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
