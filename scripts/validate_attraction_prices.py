"""Flag suspicious extractor output in data/raw/attraction_prices/<slug>.json.

Catches the "free-by-default hallucination" class of bug: extractor sees no
price text and outputs adult=0 + notes='Free admission'. Real free-admission
museums (e.g. Harvard Art Museums) are accepted only when notes quote text or
the slug is on an explicit allowlist.

Exit code 1 if any unresolved suspect is found.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PRICES = REPO / "data" / "raw" / "attraction_prices"
PAGES = PRICES / "_pages"

# Slugs whose admission is genuinely free per the museum's own statement and
# where re-running the extractor on the saved page would re-confirm it. Add a
# slug here only after you have eyeballed the page text.
ALLOWLIST_FREE = {
    "harvard-art-museums",
    "boston-harbor-islands",
    "gore-place",
}

DOLLAR_RE = re.compile(r"\$\s?\d")


def main() -> int:
    suspects: list[tuple[str, str]] = []
    for f in sorted(PRICES.glob("*.json")):
        if f.name.startswith("_"):
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        if d.get("status") != "ok":
            continue
        slug = d["slug"]
        notes = (d.get("notes") or "").lower()
        price_fields = [d.get(k) for k in ("adult", "child", "youth", "senior",
                                            "student", "military", "educator", "family")]
        all_zero_or_null = all(v in (None, 0, 0.0) for v in price_fields)
        claims_free = any(kw in notes for kw in ("free admission", "pay what you wish",
                                                  "pay what you can", "donations welcome",
                                                  "no admission"))
        if not (all_zero_or_null and claims_free):
            continue
        if slug in ALLOWLIST_FREE:
            continue
        # Heuristic: saved page mentions plenty of $-amounts → likely the
        # museum DOES charge and the extractor hallucinated.
        page = PAGES / f"{slug}.html"
        dollar_hits = 0
        if page.exists():
            dollar_hits = len(DOLLAR_RE.findall(page.read_text(encoding="utf-8", errors="ignore")))
        suspects.append((slug, f"all-zero+free notes; page $-hits={dollar_hits}"))

    if not suspects:
        print("OK: no suspect free-by-default price records.")
        return 0
    print("SUSPECT free-by-default price records (verify or mark needs_review):")
    for slug, why in suspects:
        print(f"  - {slug}: {why}")
    print(f"\n{len(suspects)} suspect(s). Either:")
    print("  (a) add slug to ALLOWLIST_FREE after confirming the page truly states free admission, or")
    print("  (b) re-extract with real prices, or")
    print("  (c) set status to 'needs_review' and null all price fields.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
