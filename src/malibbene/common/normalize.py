"""Normalize a library museum-pass benefit text into a short display label.

Ported verbatim from ``backup/normalize_benefit.py``. The regex lexical table
was derived from 278 unique benefit strings observed across 15 libraries
(2026-05-09 in the backup snapshot).

Returns ``(label, label_class)`` where ``label_class`` is one of:
  ``free`` / ``price`` / ``half`` / ``percent-off`` / ``dollar-off`` /
  ``discount`` / ``unknown``.

Callers (build / structuring step) use ``label_class`` to decide whether to
override hand-curated values in the structured matrix.

Display label format:
  - ``Free``                when admission is fundamentally free
  - ``$N``                  when a concrete per-person dollar amount is observed
                            (kid pricing and per-party caps go in the note field)
  - ``50% off``             when 50% off / 1/2 price / half price
  - ``N% off``              when a non-50 percent-off
  - ``$N off``              when a dollar-off discount
  - ``Discount``            when only a vague "discounted" wording is found
  - ``""``                  when truly unrecognized (caller falls back to curated)
"""

from __future__ import annotations

import html
import re
import unicodedata


def _money(s: str) -> str:
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


def _clean(raw: str) -> str:
    text = unicodedata.normalize("NFKC", html.unescape(raw or ""))
    return re.sub(r"\s+", " ", text).strip().lower()


# Per-person dollar amount, in priority order. Each pattern captures the
# adult/standard price; child prices are intentionally ignored — they go in
# the note field.
PRICE_PATTERNS = [
    re.compile(
        r"\$\s*(\d+(?:\.\d{1,2})?)\s*(?:per\s+(?:person|adult|visitor|guest|ticket)|/(?:person|adult|visitor|each))"
    ),
    re.compile(
        r"\$\s*(\d+(?:\.\d{1,2})?)\s+admission\s+(?:per\s+(?:person|adult|visitor|guest)|each|for\s+(?:up\s+to|each))"
    ),
    re.compile(
        r"\$\s*(\d+(?:\.\d{1,2})?)\s+co-?pay\s+(?:per\s+(?:person|adult|visitor)|for\s+adults?)"
    ),
    re.compile(
        r"\bat\s+\$\s*(\d+(?:\.\d{1,2})?)\s+(?:per\s+(?:person|adult|visitor|guest)|each|a\s+person|/(?:person|each))"
    ),
    re.compile(r"\bat\s+\$\s*(\d+(?:\.\d{1,2})?)\.00\s+(?:per|each|a\s+person)"),
    re.compile(r"\$\s*(\d+(?:\.\d{1,2})?)\s+each\b"),
    re.compile(r"\$\s*(\d+(?:\.\d{1,2})?)\s+charge\s+per\s+(?:person|adult)"),
    re.compile(r"\$\s*(\d+(?:\.\d{1,2})?)\s+(?:a\s+person|apiece)"),
    re.compile(
        r"(?:visitor|patron|adult|guest)\s+(?:will\s+be\s+|is\s+)?charged\s+\$\s*(\d+(?:\.\d{1,2})?)"
    ),
    re.compile(r"\bat\s+\$\s*(\d+(?:\.\d{1,2})?)\.00\b"),
    re.compile(r"\$\s*(\d+(?:\.\d{1,2})?)\s+for\s+adults?\b"),
    re.compile(r"\badults?\s+(?:are|:)\s*\$\s*(\d+(?:\.\d{1,2})?)"),
    re.compile(r"\$\s*(\d+(?:\.\d{1,2})?)\s+co-?pay\b"),
    re.compile(r"\$\s*(\d+(?:\.\d{1,2})?)\s+admission\b"),
]

HALF_PRICE_RE = re.compile(
    r"\bhalf[\s-]?price[ds]?\b"
    r"|\b50\s*%\s*(?:off|of(?:\s+regular)?|discount(?:\s+on)?|admission)?\b"
    r"|\b1/2\s*(?:price|admission|off)\b"
    r"|\bat\s+half\s+price\b"
    r"|\bhalf\s+(?:the\s+)?regular\s+admission\b"
    r"|\bhalf\s+off\b"
    r"|\b50\s*%\s+admission\b"
)

# Generic "free" wording. Only triggers when no concrete $-per-person amount
# was found, so "Pass admits 2 adults at $10/person; children under 6 are
# free" does NOT misclassify as free.
FREE_RE = re.compile(
    r"\bfree\s+admission\b"
    r"|\bfor\s+free\b"
    r"|\badmits\s+[\w\s,]*?(?:person|people|visitor|visitors|adult|adults|guest|guests|passengers?)\s+free\b"
    r"|\b(?:person|people|visitor|visitors|adult|adults|guests?)\s+free(?:[\s,.]|\s+of\s+charge)\b"
    r"|\bfree\s+entry\b"
    r"|\bfree\s+access\b"
    r"|\bfree\s+of\s+charge\b"
    r"|\bcomplimentary\s+admission\b"
    r"|\bno\s+admission\s+fee\b"
    r"|\badmission\s+is\s+free\b"
    r"|\bfree\s+to\s+all\b"
    r"|\ballows?\s+free\s+admission\b"
    r"|\bfree\s+parking\b"
    r"|\bunlimited\s+(?:day-?use\s+)?parking\b"
    r"|\bfree\s+(?:\w+\s+){1,4}admission\b"
    r"|\b\d+\s+free\s+(?:tickets?|tours?\s+tickets?|admissions?)\b"
    r"|\bfree\s+ride\b"
    r"|\bat\s+no\s+charge\b"
    r"|\bno\s+charge\s+(?:per|for)\b"
)

PERCENT_OFF_RE = re.compile(r"(\d{1,2})\s*%\s*(?:off|discount)")
DOLLAR_OFF_RE = re.compile(r"\$\s*(\d+(?:\.\d{1,2})?)\s+off\b")
GENERIC_DISCOUNT_RE = re.compile(r"\bdiscount(?:ed)?\b|\breduced\b")


def normalize(raw: str) -> tuple[str, str]:
    if not raw:
        return ("", "unknown")
    text = _clean(raw)

    # 1. Concrete per-person price (most specific).
    for pat in PRICE_PATTERNS:
        m = pat.search(text)
        if m:
            return (f"${_money(m.group(1))}", "price")

    # 2. Free admission — only when no concrete price was observed.
    if FREE_RE.search(text):
        return ("Free", "free")

    # 3. Half price — covers 50% off / 1/2 price / half price.
    if HALF_PRICE_RE.search(text):
        return ("50% off", "half")

    # 4. Other percent off (non-50).
    m = PERCENT_OFF_RE.search(text)
    if m and m.group(1) != "50":
        return (f"{m.group(1)}% off", "percent-off")

    # 5. Dollar-off discount.
    m = DOLLAR_OFF_RE.search(text)
    if m:
        return (f"${_money(m.group(1))} off", "dollar-off")

    # 6. Vague "discount" / "discounted" / "reduced" with no quantification.
    if GENERIC_DISCOUNT_RE.search(text):
        return ("Discount", "discount")

    return ("", "unknown")


# --- Self-test (`python -m malibbene.common.normalize`) ---
# Expectations updated from backup/ (which had stale '免费' / 'half price' /
# '$N per person' literals that no longer match the implementation).
TEST_CASES = [
    # Free
    ("Free admission for up to 4 visitors.", "Free", "free"),
    ("Pass admits 5 people for free, one pass per party.", "Free", "free"),
    ("Each pass admits 4 people for free admission.", "Free", "free"),
    ("Pass provides free parking for 1 car", "Free", "free"),
    ("Admission is free to all visitors every day.", "Free", "free"),
    ("One pass allows free admission for up to 9 people per day.", "Free", "free"),
    # Per-person price
    ("$2 admission each for up to 4 visitors.", "$2", "price"),
    ("Admits 2 people at $10.00 per person.", "$10", "price"),
    ("$12 admission per person for up to 4 visitors", "$12", "price"),
    ("Pass admits 6 people at $9 per adult and $6 per child.", "$9", "price"),
    ("Each pass admits up to 4 adults for $5 each", "$5", "price"),
    ("Pass admits 2 adults at a discounted rate of $10 per person (general admission)", "$10", "price"),
    ("Children 6 and under are admitted free. This pass admits 2 adults at a discounted rate of $10 per person.", "$10", "price"),
    # Half price
    ("Pass admits up to four people for half price.", "50% off", "half"),
    ("Pass admits 4 visitors at 50% admission per person", "50% off", "half"),
    ("The pass allows admission for up to five (5) people at 50% off.", "50% off", "half"),
    ("Admits up to 4 (adults or children) at half price per person.", "50% off", "half"),
    ("This pass admits 3 visitors at 1/2 price admission per person", "50% off", "half"),
    ("50% off admission price.", "50% off", "half"),
    # Percent off (non-50)
    ("This pass will admit up to 4 people at a 25% discount on tickets.", "25% off", "percent-off"),
    ("30% off regular admission", "30% off", "percent-off"),
    # Dollar off
    ("Get $5 off your ticket purchase.", "$5 off", "dollar-off"),
    # Vague discount
    ("Discount admission for cardholders.", "Discount", "discount"),
    # Unknown
    ("Reservations no longer accepted.", "", "unknown"),
    ("", "", "unknown"),
]


def _run_self_test() -> int:
    failures = []
    for raw, expected_label, expected_class in TEST_CASES:
        got_label, got_class = normalize(raw)
        ok = got_label == expected_label and got_class == expected_class
        marker = "OK " if ok else "FAIL"
        print(f"{marker} {got_class:11} {got_label:20} | {raw[:80]}")
        if not ok:
            failures.append((raw, (expected_label, expected_class), (got_label, got_class)))
    print()
    if failures:
        print(f"FAIL: {len(failures)}/{len(TEST_CASES)}")
        for raw, exp, got in failures:
            print(f"  expected {exp}, got {got}: {raw[:80]}")
        return 1
    print(f"PASS: {len(TEST_CASES)}/{len(TEST_CASES)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_run_self_test())
