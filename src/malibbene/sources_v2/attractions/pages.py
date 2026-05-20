from __future__ import annotations
import json, re
from pathlib import Path
from malibbene.common.http import fetch

_OG_IMG = re.compile(r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']+)["\']', re.I)
_TITLE  = re.compile(r"<title>([^<]+)</title>", re.I)

def fetch_attraction_page(slug: str, url: str, raw_root: Path) -> dict:
    html = fetch(url)
    base = raw_root / "attractions" / "pages"
    base.mkdir(parents=True, exist_ok=True)
    (base / f"{slug}.html").write_text(html, encoding="utf-8")
    title_m = _TITLE.search(html)
    og_m = _OG_IMG.search(html)
    meta = {
        "slug": slug, "url": url,
        "title": title_m.group(1).strip() if title_m else None,
        "og_image": og_m.group(1) if og_m else None,
    }
    (base / f"{slug}.meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    return meta
