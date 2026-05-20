"""LibCal policies. Mirrors Assabet policies structure."""
from __future__ import annotations

import json
from pathlib import Path

from malibbene.common.http import fetch
from malibbene.sources_v2.assabet.policies import extract_policy_text


def scrape_policies(
    library_id: str,
    card_page_url: str,
    pass_page_url: str | None,
    raw_root: Path,
) -> dict:
    card_html = fetch(card_page_url) if card_page_url else ""
    pass_html = fetch(pass_page_url) if pass_page_url else ""
    out = {
        "library_id": library_id,
        "card_page_url": card_page_url,
        "pass_page_url": pass_page_url,
        "card_page": extract_policy_text(card_html) if card_html else None,
        "pass_page": extract_policy_text(pass_html) if pass_html else None,
    }
    p = raw_root / "libcal" / "policies" / f"{library_id}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    return out
