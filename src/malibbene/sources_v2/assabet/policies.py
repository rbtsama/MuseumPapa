from __future__ import annotations

import json
import re
from pathlib import Path

from malibbene.common.http import fetch
from malibbene.common.eligibility_text import (
    classify_card_eligibility,
    classify_pass_pickup,
)


_BLOCK_RE = re.compile(r"<(?:p|li|div)[^>]*>(.*?)</(?:p|li|div)>", re.S | re.I)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def extract_policy_text(html: str) -> dict:
    """Extract a clean policy-text blob from a card / pass policy page and
    classify card eligibility + pass pickup based on word lists."""
    blocks = _BLOCK_RE.findall(html or "")
    clean: list[str] = []
    seen: set[str] = set()
    for raw in blocks:
        txt = _TAG_RE.sub("", raw)
        txt = _WS_RE.sub(" ", txt).strip()
        if not (20 < len(txt) < 4000):
            continue
        if txt in seen:
            continue
        seen.add(txt)
        clean.append(txt)

    text = "\n".join(clean[:30])
    return {
        "policy_text": text,
        "card_eligibility": classify_card_eligibility(text).value,
        "pass_pickup": classify_pass_pickup(text).value,
    }


def scrape_policies(
    library_id: str,
    card_page_url: str,
    pass_page_url: str | None,
    raw_root: Path,
    render_js: bool = False,
) -> dict:
    # Some library card pages sit behind a WAF that serves a nav-only shell to
    # plain urllib (e.g. Tewksbury). Those seeds carry requires_render_js=true,
    # which the caller forwards here so we render the page with Playwright and
    # actually get the eligibility text. Without this, a plain re-run silently
    # reverts such libs to card_eligibility=unknown.
    card_html = fetch(card_page_url, render_js=render_js) if card_page_url else ""
    pass_html = fetch(pass_page_url, render_js=render_js) if pass_page_url else ""
    out = {
        "library_id": library_id,
        "card_page_url": card_page_url,
        "pass_page_url": pass_page_url,
        "card_page": extract_policy_text(card_html) if card_html else None,
        "pass_page": extract_policy_text(pass_html) if pass_html else None,
    }
    p = raw_root / "assabet" / "policies" / f"{library_id}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    return out
