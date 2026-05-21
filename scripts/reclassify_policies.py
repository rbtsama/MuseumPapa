"""Re-run the eligibility classifier over every saved policy file.

The policy scrapers (``sources_v2/<platform>/policies.py``) classify card
eligibility + pass pickup at scrape time. When the classifier in
``malibbene.common.eligibility_text`` is improved but the underlying scraped
``policy_text`` has NOT changed, there is no need to re-fetch the pages — we just
need to re-run the classifier over the text we already have on disk.

This script walks ``data/raw/<platform>/policies/*.json`` and rewrites each file
with freshly-classified ``card_page.card_eligibility`` / ``pass_page.pass_pickup``
values, using the current classifier. It is the reproducible re-classify path
(idempotent: running it twice produces the same files).

Honesty note: it ONLY re-derives the two classification fields from the existing
``policy_text``. It never invents text and never touches ``policy_text`` itself.

Usage:
    python scripts/reclassify_policies.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from malibbene.common.eligibility_text import (  # noqa: E402
    classify_card_eligibility_with_phrase,
    classify_pass_pickup,
)


def _reclassify_page(page: dict | None) -> bool:
    """Re-derive both classification fields on one page block in place.

    ``extract_policy_text`` writes a ``card_eligibility`` AND a ``pass_pickup``
    field on every page block, so we keep both in sync here (the build only reads
    ``card_page.card_eligibility`` + ``pass_page.pass_pickup``, but re-deriving
    both avoids leaving a stale value behind after the source URL/text changes).

    Honesty invariant: a non-``unknown`` card_eligibility MUST carry the verbatim
    matched phrase in ``eligibility_source_phrase``. We always re-derive that
    phrase from the current text; if the classifier returns ``unknown`` we clear
    the phrase. This guarantees every classified value is auditable and that a
    value can never outlive the text that justified it.
    """
    if page is None:
        return False
    text = page.get("policy_text", "")
    changed = False
    new_card, phrase = classify_card_eligibility_with_phrase(text)
    if page.get("card_eligibility") != new_card.value:
        page["card_eligibility"] = new_card.value
        changed = True
    new_phrase = phrase if new_card.value != "unknown" else None
    if page.get("eligibility_source_phrase") != new_phrase:
        page["eligibility_source_phrase"] = new_phrase
        changed = True
    new_pickup = classify_pass_pickup(text).value
    if page.get("pass_pickup") != new_pickup:
        page["pass_pickup"] = new_pickup
        changed = True
    return changed


def reclassify_file(path: Path) -> tuple[bool, str, str]:
    """Re-classify one policy file in place.

    Returns (changed, card_eligibility, pass_pickup) where the reported values
    are the build-relevant ones: ``card_page.card_eligibility`` and
    ``pass_page.pass_pickup``.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    changed = False
    changed |= _reclassify_page(data.get("card_page"))
    changed |= _reclassify_page(data.get("pass_page"))

    card = data.get("card_page") or {}
    passp = data.get("pass_page") or {}
    card_elig = card.get("card_eligibility", "unknown")
    pass_pickup = passp.get("pass_pickup", "unknown")

    if changed:
        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    return changed, card_elig, pass_pickup


def main() -> None:
    raw_root = ROOT / "data" / "raw"
    files = sorted(raw_root.glob("*/policies/*.json"))
    n_changed = 0
    for path in files:
        changed, card_elig, pass_pickup = reclassify_file(path)
        flag = "*" if changed else " "
        print(f"{flag} {path.stem:18} card={card_elig:13} pickup={pass_pickup}")
        if changed:
            n_changed += 1
    print(f"\nre-classified {len(files)} files; {n_changed} changed")


if __name__ == "__main__":
    main()
