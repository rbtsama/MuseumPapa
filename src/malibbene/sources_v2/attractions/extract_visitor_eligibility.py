"""Deterministic visitor-eligibility extractor.

Reads the attraction landing page HTML (data/raw/attractions/pages/<slug>.html)
plus any subpages (data/raw/attractions/subpages/<slug>__*.html), and returns:

    {
      "residency": "ma_resident" | "town_resident" | "none" | "unknown",
      "scope":   optional town/state string,
      "locals_free": bool,
      "note":   short rule-tag describing why the verdict was reached,
      "source_phrase": verbatim 180-char window around the matched cue, or null
    }

Rules:
- Strip HTML tags to a flat text stream.
- Look for the keyword "resident" with surrounding 80-char context.
- Reject false positives: President, Vice President, "former residents",
  animal "resident" mentions ("resident otter", "resident sheep"), privacy-
  policy clauses ("Nevada residents", "California residents"), and donor
  clubs like "President's Circle".
- "Massachusetts residents" / "MA residents" -> residency=ma_resident,
  locals_free hint based on nearby "free admission" within +-80 chars.
- "<Town> residents" + "free" within +-120 chars -> locals_free=true,
  residency=none (since the museum is open to all but locals get a perk).
- Otherwise residency=unknown.

This is conservative on purpose: ambiguous mentions stay "unknown" rather
than fabricating data.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")

# False positives — when these match within +-15 chars we ignore the hit.
_FALSE_POSITIVES = re.compile(
    r"\b("
    r"president(?:s|'s|s'|’s)?(?:\s+(?:circle|club|fellows|of))?"
    r"|vice[\s-]?president(?:s)?"
    r"|former\s+residents?"
    r"|historic\s+residents?"
    r"|first\s+residents?"
    r"|past\s+residents?"
    r"|resident\s+(?:otter|sheep|owl|fox|bird|animal|fish|cow|goat|horse|deer|turtle|raccoon|opossum|hen|chicken|rabbit|snake)"
    r"|nevada\s+residents?"
    r"|california\s+residents?"
    r"|colorado\s+residents?"
    r"|virginia\s+residents?"
    r"|residents?\s+and\s+visitors"
    r"|resident\s+(?:director|artist|curator|scholar|fellow|composer|playwright|company)"
    r")\b",
    re.I,
)

_MA_RESIDENT = re.compile(
    r"\b(massachusetts|ma)\s+residents?\b",
    re.I,
)

_TOWN_RESIDENT = re.compile(
    r"\b([A-Z][A-Za-z'\.\-]+(?:[\s-][A-Z][A-Za-z'\.\-]+)?)\s+residents?\b",
)
# Bare "residents" hits handled separately via FREE-context window.

_FREE_NEAR = re.compile(
    r"\b(free\s+admission|admission\s+is\s+free|admit(?:ted)?\s+free|free\s+entry|locals\s+free)\b",
    re.I,
)


def html_to_text(html: str) -> str:
    """Strip tags + collapse whitespace, returning a single flat string."""
    # Remove script/style blocks entirely
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.I | re.S)
    text = _TAG.sub(" ", html)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
    text = _WS.sub(" ", text).strip()
    return text


def _gather_html(slug: str, raw_root: Path) -> str:
    parts: list[str] = []
    page = raw_root / "attractions" / "pages" / f"{slug}.html"
    if page.exists():
        parts.append(page.read_text(encoding="utf-8", errors="ignore"))
    sub_dir = raw_root / "attractions" / "subpages"
    if sub_dir.exists():
        for f in sorted(sub_dir.glob(f"{slug}__*.html")):
            parts.append(f.read_text(encoding="utf-8", errors="ignore"))
    return "\n".join(parts)


def _window(text: str, start: int, end: int, pad: int = 80) -> str:
    a = max(0, start - pad)
    b = min(len(text), end + pad)
    return text[a:b].strip()


def extract_visitor_eligibility(slug: str, raw_root: Path) -> dict[str, Any]:
    html = _gather_html(slug, raw_root)
    if not html:
        return {
            "status": "ok",
            "extracted": {
                "residency": "unknown", "scope": None, "locals_free": False,
                "note": "no html available", "source_phrase": None,
            },
        }
    text = html_to_text(html)

    # Find genuine resident mentions
    real_hits: list[tuple[int, int, str]] = []
    for m in re.finditer(r"residents?\b", text, re.I):
        local = text[max(0, m.start() - 25): m.end() + 5]
        if _FALSE_POSITIVES.search(local):
            continue
        real_hits.append((m.start(), m.end(), local))

    if not real_hits:
        return {
            "status": "ok",
            "extracted": {
                "residency": "unknown", "scope": None, "locals_free": False,
                "note": "no residency policy found on page",
                "source_phrase": None,
            },
        }

    # Look for MA-residency hint
    ma_m = _MA_RESIDENT.search(text)
    if ma_m:
        local = text[max(0, ma_m.start() - 25): ma_m.end() + 5]
        if not _FALSE_POSITIVES.search(local):
            window = _window(text, ma_m.start(), ma_m.end(), 80)
            locals_free = bool(_FREE_NEAR.search(window))
            return {
                "status": "ok",
                "extracted": {
                    "residency": "ma_resident", "scope": "MA",
                    "locals_free": locals_free, "note": "MA residents mentioned",
                    "source_phrase": window[:180],
                },
            }

    # Town-resident scan: if any town-residents mention is *within* 60 chars
    # of "free", we say locals_free=true with residency=none (the museum is
    # open to all but a discount/free day exists for locals).
    for start, end, _ in real_hits:
        window = _window(text, start, end, 100)
        if _FREE_NEAR.search(window):
            # Try to find the leading capitalised token as the town.
            preface = text[max(0, start - 60): start]
            m = re.search(r"([A-Z][A-Za-z'\.\-]+(?:[\s-][A-Z][A-Za-z'\.\-]+)?)\s+$", preface)
            scope = m.group(1) if m else None
            return {
                "status": "ok",
                "extracted": {
                    "residency": "none", "scope": scope,
                    "locals_free": True,
                    "note": f"locals-free day mentioned for {scope or 'town residents'}",
                    "source_phrase": _window(text, start, end, 90)[:180],
                },
            }

    # Mentions of residents exist but no FREE association -> unknown.
    return {
        "status": "ok",
        "extracted": {
            "residency": "unknown", "scope": None, "locals_free": False,
            "note": "ambiguous residency mention, no free-admission association",
            "source_phrase": real_hits[0][2][:180] if real_hits else None,
        },
    }
