"""Deterministic reservation-policy extractor.

Output schema:

    {
      "required": "none" | "timed_entry" | "walk_in_ok",
      "booking_url": str | null,
      "lead_time_hours": int | null,
      "pass_holder_path": "promo_code_in_general_checkout" |
                          "dedicated_pass_sku" |
                          "dedicated_pass_holders_url" |
                          "library_only" | "unknown",
      "pass_holder_url": str | null,
      "notes": short rule-tag,
      "source_phrase": 180-char window around the matched cue
    }

Rules:
- Search HTML text for cues like "timed entry required", "reserve your time
  slot", "advance reservation required", "walk-ins welcome", "no reservation
  needed". Defaults to walk_in_ok with a note when no cue is found.
- booking_url: first <a href> link to a known booking host
  (ticketmaster, etix, universe, showclix, museumtix, embarktickets,
   eventbrite, showpass, tixr, ticketleap, acmeticketing, tessitura,
   vivenu, patronmanager, fareharbor.com) OR a href containing
  /tickets, /book, /reserve, /admission.
- pass_holder_url: a href whose visible text or URL path mentions
  "library pass" / "library passes" / "pass holders" -> dedicated_pass_holders_url.
- lead_time_hours: 0 when walk-ins welcome; null otherwise (we don't
  attempt to parse "24 hours in advance" etc. — too brittle).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .extract_visitor_eligibility import html_to_text, _gather_html  # noqa: E501


_TIMED = re.compile(
    r"\b(timed[\s-]?entry(?:\s+required)?|reserve\s+your\s+time\s+slot|"
    r"advance\s+reservations?\s+required|book\s+a\s+timed\s+ticket|"
    r"timed\s+ticket\s+required|tickets?\s+must\s+be\s+reserved\s+in\s+advance)\b",
    re.I,
)
_WALK_IN = re.compile(
    r"\b(walk-?ins?\s+welcome|no\s+reservation\s+(?:needed|required)|"
    r"reservations?\s+(?:are\s+)?not\s+required|drop-?in\s+welcome)\b",
    re.I,
)

# Anchor href + visible-text patterns
_ANCHOR = re.compile(r'<a\b[^>]*?\bhref=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
                     re.I | re.S)

_BOOKING_HOSTS = (
    "ticketmaster", "etix.com", "universe.com", "showclix", "museumtix",
    "embarktickets", "eventbrite.com", "showpass", "tixr", "ticketleap",
    "acmeticketing", "tessitura", "vivenu", "patronmanager", "fareharbor.com",
)
_BOOKING_PATHS = (
    "/tickets", "/book", "/reserve", "/admission", "/buy-tickets",
    "/purchase-tickets", "/ticketing", "/ferry-tickets", "/visit/",
    "/plan-your-visit", "/plan-a-visit",
)

_PASS_HOLDER_TEXT = re.compile(
    r"\b(library\s+pass(?:es)?(?:\s+program)?|pass\s+holders?|library-?pass-?program)\b",
    re.I,
)
_PASS_HOLDER_PATH = re.compile(
    r"(library[-_/]pass|pass[-_/]holders?|library-pass-program)",
    re.I,
)


def _find_booking_url(html: str) -> str | None:
    for m in _ANCHOR.finditer(html):
        href = m.group(1)
        href_l = href.lower()
        if any(host in href_l for host in _BOOKING_HOSTS):
            return href
        if any(p in href_l for p in _BOOKING_PATHS):
            # Avoid mailto, anchors, javascript
            if href.startswith(("http://", "https://", "/")):
                return href
    return None


def _find_pass_holder_url(html: str) -> str | None:
    for m in _ANCHOR.finditer(html):
        href = m.group(1)
        visible = re.sub(r"<[^>]+>", " ", m.group(2))
        visible = re.sub(r"\s+", " ", visible).strip()
        if _PASS_HOLDER_PATH.search(href) or _PASS_HOLDER_TEXT.search(visible):
            if href.startswith(("http://", "https://", "/")):
                return href
    return None


def extract_reservation(slug: str, raw_root: Path) -> dict[str, Any]:
    html = _gather_html(slug, raw_root)
    if not html:
        return {
            "status": "ok",
            "extracted": {
                "required": "walk_in_ok", "booking_url": None,
                "lead_time_hours": None, "pass_holder_path": "unknown",
                "pass_holder_url": None, "notes": "no html available",
                "source_phrase": None,
            },
        }

    text = html_to_text(html)
    timed_m = _TIMED.search(text)
    walkin_m = _WALK_IN.search(text)

    if timed_m:
        required = "timed_entry"
        window = text[max(0, timed_m.start() - 80): timed_m.end() + 80]
        notes = "timed-entry cue found"
        lead = None
    elif walkin_m:
        required = "walk_in_ok"
        window = text[max(0, walkin_m.start() - 80): walkin_m.end() + 80]
        notes = "walk-in welcome"
        lead = 0
    else:
        required = "walk_in_ok"
        window = ""
        notes = "no explicit reservation language; defaulted to walk_in_ok"
        lead = 0

    booking_url = _find_booking_url(html)
    pass_url = _find_pass_holder_url(html)
    pass_path = "dedicated_pass_holders_url" if pass_url else "unknown"

    return {
        "status": "ok",
        "extracted": {
            "required": required,
            "booking_url": booking_url,
            "lead_time_hours": lead,
            "pass_holder_path": pass_path,
            "pass_holder_url": pass_url,
            "notes": notes,
            "source_phrase": window[:180] if window else None,
        },
    }
