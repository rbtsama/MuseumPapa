"""Deterministic admission-price extractor.

Output schema:

    {"prices": [
      {"audience": "adult"|"child"|"senior"|"youth"|"student"|"military"|"educator"|"family",
       "price": float | null,
       "age_range": {"min": int, "max": int} | null,
       "source_phrase": short verbatim window}
    ]}

Rules:
- Scan HTML text for "$N" or "$N.NN" tokens.
- For each price, look at +-60 char context for an audience-label keyword.
- Reject if the context contains a *negative* keyword
  (membership/program/class/career/special-event/sensory/donate/parking/parking
  fee/late-fee/fine/per-day).
- Multiple appearances of the same audience+price are deduplicated.
- Scans the landing page AND any subpages.
- If no price tokens at all, returns an empty list (still status=ok).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .extract_visitor_eligibility import html_to_text, _gather_html


_AUDIENCE_KEYWORDS = [
    ("adult", re.compile(r"\b(adults?(?:\s*\(?[\s\d+\-]+\)?)?)\b", re.I)),
    ("senior", re.compile(r"\b(seniors?(?:\s*\(?[\d+\s-]+\)?)?|age\s+65\+|seniors?\s+65\+)\b", re.I)),
    ("youth", re.compile(r"\b(youths?(?:\s*\(?[\d\s-]+\)?)?)\b", re.I)),
    ("student", re.compile(r"\b(students?(?:\s+\(?with\s*id\)?)?)\b", re.I)),
    ("military", re.compile(r"\b(military|veterans?|active\s+duty)\b", re.I)),
    ("educator", re.compile(r"\b(educators?|teachers?)\b", re.I)),
    ("family", re.compile(r"\b(family|families|family\s+pass)\b", re.I)),
    ("child", re.compile(r"\b(child(?:ren)?|kids?(?:\s*\(?[\d\s-]+\)?)?)\b", re.I)),
]

_NEG_CTX = re.compile(
    r"\b(membership|program(?:s|me)?|class(?:es)?|career|special\s+event|"
    r"sensory|donat(?:e|ion)|parking\s+fee|parking\s+pass|late\s+fee|"
    r"fine|per\s+day|admission\s+per\s+day|extra\s+fee|gift\s+shop|"
    r"benefit|annual\s+pass|fundraiser|gala|membership\s+level|"
    r"book\s+(?:fair|sale)|workshop|summer\s+camp|registration|"
    r"online\s+only\s+rate|service\s+fee)\b",
    re.I,
)

_PRICE_TOKEN = re.compile(r"\$\s*(\d+(?:\.\d{1,2})?)")
_AGE_RANGE = re.compile(r"\(\s*(\d+)\s*[-–]\s*(\d+)\s*\)", re.I)


def extract_prices(slug: str, raw_root: Path) -> dict[str, Any]:
    html = _gather_html(slug, raw_root)
    out_rows: list[dict[str, Any]] = []
    if not html:
        return {"status": "ok", "extracted": {"prices": out_rows}}

    text = html_to_text(html)
    seen: set[tuple[str, float]] = set()

    for m in _PRICE_TOKEN.finditer(text):
        price = float(m.group(1))
        if price <= 0 or price > 500:
            continue
        # Examine a tighter window for negative context (parking fee /
        # membership / per-day / etc.) — restrict to 40 chars to avoid
        # spillover poisoning legitimate adult/child prices.
        neg_ctx = text[max(0, m.start() - 35): m.end() + 35]
        if _NEG_CTX.search(neg_ctx):
            continue

        ctx = text[max(0, m.start() - 60): m.end() + 60]
        rel_start = min(m.start(), 60)

        # Find the audience keyword *nearest* to the price token.
        best: tuple[int, str, "re.Match[str]"] | None = None
        for label, pat in _AUDIENCE_KEYWORDS:
            for am in pat.finditer(ctx):
                # Distance from price token in ctx coordinates
                dist = min(
                    abs(am.start() - rel_start),
                    abs(am.end() - rel_start),
                )
                if best is None or dist < best[0]:
                    best = (dist, label, am)
        if best is None:
            continue
        label = best[1]
        if (label, price) in seen:
            continue

        age_m = _AGE_RANGE.search(ctx)
        age_range = (
            {"min": int(age_m.group(1)), "max": int(age_m.group(2))}
            if age_m else None
        )
        out_rows.append({
            "audience": label,
            "price": price,
            "age_range": age_range,
            "source_phrase": ctx.strip()[:200],
        })
        seen.add((label, price))

    return {"status": "ok", "extracted": {"prices": out_rows}}
