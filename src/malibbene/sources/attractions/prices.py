"""Attraction admission page fetcher.

Tries common URL paths (/admission, /tickets, /visit, ...), saves first non-trivial
response as HTML. Extraction (adult/child/senior prices) is done downstream by a
subagent reading the saved HTML.

Falls back to Playwright (render_js=True) when static fetch returns a near-empty body.
"""
from __future__ import annotations

from pathlib import Path

from malibbene.common.http import fetch

CANDIDATE_PATHS = [
    "/admission", "/tickets", "/visit/admission", "/visit/tickets",
    "/plan-your-visit", "/visit", "/hours-admission", "/hours", "/",
]
_MIN_BODY_BYTES = 500


def fetch_one(slug: str, base_url: str, *, out_dir: Path) -> dict:
    """Fetch admission/tickets page for an attraction; save first non-trivial HTML."""
    out_dir.mkdir(parents=True, exist_ok=True)
    base = base_url.rstrip("/")
    last_error = "no_path_returned_useful_body"
    for path in CANDIDATE_PATHS:
        url = base + path
        try:
            html = fetch(url)
        except Exception as e:
            last_error = f"fetch_failed:{e}"
            continue
        if len(html) < _MIN_BODY_BYTES:
            # Try JS-rendered fallback
            try:
                html = fetch(url, render_js=True, force=True)
            except Exception as e:
                last_error = f"render_js_failed:{e}"
                continue
            if len(html) < _MIN_BODY_BYTES:
                last_error = "html_too_short_even_with_js"
                continue
        out_path = out_dir / f"{slug}.html"
        out_path.write_text(html, encoding="utf-8")
        return {"slug": slug, "status": "ok", "source_url": url, "bytes": len(html)}
    return {"slug": slug, "status": f"failed:{last_error}"}
