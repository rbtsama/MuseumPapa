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
    r"online\s+only\s+rate|service\s+fee|"
    # Donation widgets (USS Constitution "Give Amount $2,500 ...").
    r"give\s+amount|ways?\s+to\s+support|pledge)\b",
    re.I,
)

# Suggested-donation admission tiers (e.g. USS Constitution Museum). The label
# immediately preceding the price selects intent: only the baseline "Standard"
# (or "Suggested"/"General") tier is a usable admission price; "Pay it Forward"
# and "Reduced" are optional above/below tiers we do NOT record.
_TIER_KEEP = re.compile(r"\b(standard|suggested)\b", re.I)
_TIER_DROP = re.compile(r"\b(pay\s+it\s+forward|reduced|donat)\b", re.I)

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

        # Suggested-donation tier handling: the label directly preceding the
        # price ("Pay it Forward:" / "Standard:" / "Reduced:") is decisive.
        preface = text[max(0, m.start() - 20): m.start()]
        if _TIER_DROP.search(preface):
            # Optional above/below suggested tier -> not a recorded price.
            continue
        forced_label: str | None = None
        if _TIER_KEEP.search(preface):
            forced_label = "adult"

        ctx = text[max(0, m.start() - 60): m.end() + 60]
        rel_start = min(m.start(), 60)

        if forced_label is not None:
            if (forced_label, price) not in seen:
                age_m0 = _AGE_RANGE.search(ctx)
                out_rows.append({
                    "audience": forced_label,
                    "price": price,
                    "age_range": (
                        {"min": int(age_m0.group(1)), "max": int(age_m0.group(2))}
                        if age_m0 else None
                    ),
                    "source_phrase": ctx.strip()[:200],
                })
                seen.add((forced_label, price))
            continue

        # Strong bind: a label that immediately FOLLOWS the price across a
        # dash/colon separator — "$10.00 – Seniors", "$15: Adults". This list
        # format puts the audience after its own price, so the following label
        # is authoritative and beats the generic nearest-keyword search (which
        # would otherwise grab the *previous* row's trailing label).
        label: str | None = None
        tail = text[m.end(): m.end() + 22]
        bind = re.match(r"\s*[-–—:]\s*([A-Za-z][\w '()/+]*)", tail)
        if bind:
            seg = bind.group(0)
            for lab, pat in _AUDIENCE_KEYWORDS:
                if pat.search(seg):
                    label = lab
                    break

        # Otherwise: the audience keyword *nearest* to the price token.
        if label is None:
            best: tuple[int, str, "re.Match[str]"] | None = None
            for lab, pat in _AUDIENCE_KEYWORDS:
                for am in pat.finditer(ctx):
                    dist = min(
                        abs(am.start() - rel_start),
                        abs(am.end() - rel_start),
                    )
                    if best is None or dist < best[0]:
                        best = (dist, lab, am)
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
