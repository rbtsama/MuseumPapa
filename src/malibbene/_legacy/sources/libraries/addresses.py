"""Library main-site page fetcher.

Strategy: try common URL paths (/visit, /hours, /contact, /about, /locations, /),
save the first non-trivial response as raw HTML. Extraction (street/city/state/zip)
is done downstream by a subagent reading the saved HTML.
"""
from __future__ import annotations

from pathlib import Path

from malibbene.common.http import fetch

CANDIDATE_PATHS = ["/visit", "/hours", "/contact", "/about", "/locations", "/"]
_MIN_BODY_BYTES = 200


def fetch_one(lib_id: str, base_url: str, *, out_dir: Path) -> dict:
    """Fetch a library's main site; save first OK response to ``out_dir/<lib_id>.html``.

    Returns a status dict; does NOT extract address (that's a later subagent task).
    """
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
            last_error = "html_too_short"
            continue
        out_path = out_dir / f"{lib_id}.html"
        out_path.write_text(html, encoding="utf-8")
        return {"lib_id": lib_id, "status": "ok", "source_url": url, "bytes": len(html)}
    return {"lib_id": lib_id, "status": f"failed:{last_error}"}
