"""LibCal catalog scraper. Covers BPL/Cambridge/Brookline/Braintree/Milton.

LibCal pass URLs look like ``https://<sub>.libcal.com/passes/<id>`` where
``<id>`` is either a 12-hex code (BPL/Braintree/Milton), a kebab-case slug
(Cambridge), or a short code (Brookline). Each pass appears multiple times on
the index page (title link + "Book Now" link), so we dedupe by id.
"""
from __future__ import annotations
import html as html_mod
import json
import re
from pathlib import Path

from malibbene.common.http import fetch, fetch_and_save_html


# Match <a href="/passes/<id>">title</a>. The id is alphanumeric (with - and _),
# at least 3 chars, and never the reserved literal "passes" (the listing page
# itself). Excluding chars: "/", "?", "#", '"', "<".
_PASS_LINK = re.compile(
    r'<a[^>]+href="([^"]*?/passes/([A-Za-z0-9][A-Za-z0-9_-]{2,}))"[^>]*>([^<]+)</a>',
    re.I,
)
_RESERVED_IDS = {"passes"}


def _slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "unknown"


def parse_libcal_index(html: str, library_id: str) -> list[dict]:
    items: list[dict] = []
    seen: set[str] = set()
    for url, pid, title in _PASS_LINK.findall(html):
        if pid in _RESERVED_IDS or pid in seen:
            continue
        title_clean = html_mod.unescape(title).strip()
        # Skip "Book Now" / empty / button-style links — keep the real title link.
        if not title_clean or title_clean.lower() in {"book now", "reserve", "book"}:
            continue
        seen.add(pid)
        slug = _slugify(title_clean)
        items.append({
            "library_id": library_id,
            "libcal_pass_id": pid,
            "attraction_slug": slug,
            "title": title_clean,
            "detail_url": url if url.startswith("http") else None,
            "benefit_text": None,
            "source_phrases": [],
        })
    return items


def scrape_library(library_id: str, base_url: str, raw_root: Path) -> dict:
    """Full flow: fetch /passes/ index → fetch each detail → write raw json."""
    index_url = base_url.rstrip("/") + "/passes/"
    html = fetch(index_url)
    passes = parse_libcal_index(html, library_id)

    # Reconstruct absolute detail URLs for relative hrefs.
    base = base_url.rstrip("/")
    for p in passes:
        if not p["detail_url"]:
            p["detail_url"] = f"{base}/passes/{p['libcal_pass_id']}"

    # The availability endpoint requires a 12-hex internal museum id (the
    # `museum:` JS variable on the pass detail page) — NOT the URL slug. Some
    # libraries put the hex code directly in the URL (BPL/Braintree/Milton),
    # others use a short code (Brookline = "BCM") or kebab slug (Cambridge),
    # in which case we MUST scrape the detail page to find the real museum id.
    _MUSEUM_VAR_RE = re.compile(
        r"museum\s*:\s*['\"]([a-f0-9]{8,})['\"]", re.I
    )
    detail_dir = raw_root / "libcal" / "_html" / library_id
    for p in passes:
        if p["detail_url"]:
            html_path = fetch_and_save_html(
                p["detail_url"], detail_dir / f"{p['attraction_slug']}.html"
            )
            txt = html_path.read_text(encoding="utf-8")
            paras = re.findall(r"<p[^>]*>(.*?)</p>", txt, re.S | re.I)
            clean = [re.sub(r"<[^>]+>", "", x).strip() for x in paras]
            clean = [c for c in clean if 10 < len(c) < 2000]
            p["benefit_text"] = "\n".join(clean[:8])
            p["source_phrases"] = clean
            m = _MUSEUM_VAR_RE.search(txt)
            if m:
                p["libcal_museum_id"] = m.group(1)

    out = raw_root / "libcal" / "catalog" / f"{library_id}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {"library_id": library_id, "index_url": index_url, "passes": passes},
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return {"library_id": library_id, "n_passes": len(passes), "out": str(out)}
