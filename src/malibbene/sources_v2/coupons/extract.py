"""Deterministic coupon extractor.

Input:  library_id, attraction_slug, benefit_text, source_phrases.
Output: {"status":"ok","extracted": {pass_form, coupon, restrictions}}
        or {"status":"failed","error": "..."}.

The extractor is intentionally rule-based (regex + small lexicons) so that
re-running it on the same input is byte-for-byte reproducible. It tries to
match the shape that the LLM subagents produced when they originally built the
raw/<platform>/coupons/*.json files, but it is not expected to be 100% byte
equivalent with those LLM outputs because the LLM often picked subjective
note text or hand-cropped quote windows. See scripts/extract_coupons.py for
the orchestration entry point and tests/test_coupons_extract.py for spec
examples covering each form (percent-off, dollar-off, per-person, free,
BOGO, generic discount, and the navigation-only "failed" case).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Text normalisation helpers
# ---------------------------------------------------------------------------

_HTML_ENT = {
    "&nbsp;": " ", "&amp;": "&", "&quot;": '"', "&#39;": "'", "&rsquo;": "'",
    "&lsquo;": "'", "&ldquo;": '"', "&rdquo;": '"', "&ndash;": "-", "&mdash;": "-",
}

_WORD_NUM = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
}

# Navigation-only sentences: when the entire benefit_text is one of these,
# we report "failed: no benefit text available".
_NAV_ONLY_PATTERNS = [
    re.compile(r"^\s*to choose a date for your reservation,?\s*please click on the number of the desired day\.?\s*$", re.I),
    re.compile(r"^\s*click on the desired day\.?\s*$", re.I),
    re.compile(r"^\s*please select a date\.?\s*$", re.I),
]


def _clean(s: str) -> str:
    """Replace common HTML entities and collapse whitespace."""
    if not s:
        return ""
    for k, v in _HTML_ENT.items():
        s = s.replace(k, v)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _join_source(source_phrases: list[str] | None, benefit_text: str) -> str:
    if source_phrases:
        joined = " ".join(_clean(p) for p in source_phrases if p)
    else:
        joined = _clean(benefit_text)
    return joined


def _phrase_window(text: str, width: int = 280) -> str:
    """Truncate to ``width`` characters without trailing partial word."""
    text = _clean(text)
    if len(text) <= width:
        return text
    return text[:width]


def _word_or_digit_to_int(token: str) -> int | None:
    t = token.lower().strip()
    if t.isdigit():
        return int(t)
    return _WORD_NUM.get(t)


# ---------------------------------------------------------------------------
# Capacity extraction
# ---------------------------------------------------------------------------

# Match patterns like "admits up to 4", "admits 2 visitors", "pass admits 6 people",
# "admit up to six (6) people", "for a group of up to 6 individuals", etc.
_CAP_PATTERNS = [
    re.compile(
        r"\b(?:admits?|admit|allow(?:s)?|good for|for a group of)\s+"
        r"(?:up to\s+)?(?:up to a maximum of\s+)?"
        r"(?P<num>\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)"
        r"(?:\s*\([^)]*\))?"
        r"\s+(?P<unit>people|persons?|visitors?|guests?|adults|individuals|family members|members|tickets?|admissions?)",
        re.I,
    ),
    re.compile(
        r"\bup to\s+(?P<num>\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)"
        r"(?:\s*\([^)]*\))?"
        r"\s+(?P<unit>people|persons?|visitors?|guests?|individuals|tickets?|admissions?)",
        re.I,
    ),
    re.compile(
        r"\b(?P<num>\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)"
        r"(?:\s*\([^)]*\))?"
        r"\s+(?:free\s+)?(?P<unit>tickets?|passes?|admissions?)",
        re.I,
    ),
]

# Vehicle / parking-pass capacity. Only treat as a *vehicle* benefit when the
# pass itself is a parking / per-vehicle benefit — not when "parking" appears
# inside an exclusion clause ("not valid at parking kiosks") or when "car"
# is just part of a museum name ("America's Oldest Car Collection").
_VEHICLE_HINT = re.compile(
    r"\b("
    r"per\s+vehicle"
    r"|(?:one|1|\d+)\s+vehicles?\b"
    r"|your\s+vehicle"
    r"|in\s+(?:your|the)\s+(?:car|vehicle)"
    r"|displayed\s+in\s+your\s+vehicle"
    r"|parkspass"
    r"|day-use\s+parking"
    r"|free\s+(?:general\s+|daytime\s+)?parking"
    r"|unlimited\s+parking"
    r"|parking\s+(?:access|pass\b|fee|facilit)"
    r"|admits?\s+\d+\s+cars?\b"
    r"|\d+\s+cars?\s+(?:and\s+passengers|into|to)"
    r"|one\s+carload|\d+\s+carloads?"
    r")",
    re.I,
)
# Exclusion clauses where "parking" / "state park" must NOT mean a vehicle
# benefit: Trustees "not valid at parking kiosks", "does not include State
# Park admission", "Park fees are $X".
_VEHICLE_NEG = re.compile(r"parking\s+kiosks?|park\s+admission|park\s+fees?", re.I)

# Patterns that mean ticket-capacity rather than people-count
_TICKET_HINT = re.compile(r"\b(ticket|coupon code covers|tickets per)\b", re.I)


@dataclass
class Capacity:
    kind: str = "unspecified"  # people | vehicle | ticket | unspecified
    n: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "n": self.n}


def extract_capacity(text: str) -> Capacity:
    t = _clean(text)
    # Vehicle / parking pass takes precedence — but only if the "parking" hit
    # is not solely the "not valid at parking kiosks" exclusion clause.
    veh = _VEHICLE_HINT.search(t)
    if veh:
        hit = veh.group(0)
        if not (_VEHICLE_NEG.search(hit) or "kiosk" in t[veh.start():veh.end() + 6].lower()):
            return Capacity(kind="vehicle", n=1)

    for pat in _CAP_PATTERNS:
        m = pat.search(t)
        if not m:
            continue
        n = _word_or_digit_to_int(m.group("num"))
        if n is None:
            continue
        unit = m.group("unit").lower()
        if "ticket" in unit or "admission" in unit:
            kind = "ticket" if "ticket" in unit else "people"
        else:
            kind = "people"
        return Capacity(kind=kind, n=n)
    return Capacity()


# ---------------------------------------------------------------------------
# Pass form (digital_email / physical_circ / physical_coupon)
# ---------------------------------------------------------------------------

_DIGITAL_PATTERNS = re.compile(
    r"\b("
    r"print(?:able)?\s+from\s+home"
    r"|printable[/\s-]+digital\s+coupon"
    r"|print[/\s-]+digital\s+coupon"
    r"|digital\s+pass(?:es)?"
    r"|digital\s+coupon"
    r"|e-coupon|e\s+coupon"
    r"|downloadable\s+via\s+email"
    r"|electronic\s+pass"
    r"|email(?:ed)?\s+(?:link|pass|coupon)"
    r"|link\s+delivered\s+by\s+email"
    r"|promo[_\s-]?code"
    r")\b",
    re.I,
)
_CIRC_PATTERNS = re.compile(
    r"\b("
    r"must\s+be\s+picked\s+up"
    r"|must\s+be\s+returned"
    r"|circulating\s+pass"
    r"|returnable\s+pass"
    r"|this\s+is\s+a\s+returnable\s+pass"
    r"|physical\s+pass\s+that\s+must\s+be\s+picked\s+up"
    r"|please\s+(?:pick\s+up|return)\s+(?:the\s+)?pass"
    r"|pickup\s+the\s+pass"
    r")\b",
    re.I,
)


def classify_pass_form(text: str, slug: str = "", platform: str = "assabet") -> str:
    t = _clean(text)
    # Slug-level signals (libcal puts the channel in the attraction slug)
    slug_l = slug.lower()
    if "e-coupon" in slug_l or "promo-code" in slug_l or "e-ticket" in slug_l \
            or "digital-coupon" in slug_l or "e-pass" in slug_l:
        return "digital_email"
    if "physical-pass" in slug_l:
        # Could be circulating or coupon — text rules below decide.
        pass

    if _DIGITAL_PATTERNS.search(t):
        return "digital_email"
    if _CIRC_PATTERNS.search(t):
        return "physical_circ"

    # Fallback by platform
    if platform == "libcal":
        return "physical_coupon"
    return "physical_coupon"


# ---------------------------------------------------------------------------
# Audience policies + form extraction
# ---------------------------------------------------------------------------

# Negative context: "regular admission was $X" comparisons must not produce a
# per-person policy. We strip them out before scanning for prices.
_NEG_CTX = [
    re.compile(r"regular\s+admission(?:\s+is| was| of|:)?\s*\$\d+(\.\d+)?", re.I),
    re.compile(r"regular\s+(?:adult|child|senior|youth|museum)\s+admission(?:\s+is| was| of|:)?\s*\$\d+(\.\d+)?", re.I),
    re.compile(r"regular(?:ly)?\s*\$\d+(\.\d+)?", re.I),
    re.compile(r"overdue\s+passes?\s+are\s+subject\s+to\s+a?\s*fine\s+of\s+\$\d+(\.\d+)?", re.I),
    re.compile(r"\$\d+(\.\d+)?\s+(?:per\s+day|fine|late fee)", re.I),
    re.compile(r"\(regular\s+admission:?\s*\$\d+(\.\d+)?(?:/\$\d+(\.\d+)?)?\)", re.I),
]


def _strip_negative_ctx(text: str) -> str:
    for pat in _NEG_CTX:
        text = pat.sub(" ", text)
    return text


_FREE_HEADLINE = re.compile(
    r"\b(free\s+admission|free\s+general\s+admission|free\s+entry|no\s+charge|complimentary|"
    r"free\s+parking|free\s+general\s+parking|free\s+daytime\s+parking|"
    r"for\s+free|free\s+of\s+charge|at\s+no\s+cost|with\s+no\s+cost|"
    r"unlimited\s+parking|parking\s+access|day\s+membership|"
    r"\d+\s+free\s+admissions?|\bfree\s+coupon\s+pass|free\s+coupon|"
    r"\d+\s+people\s+free|\d+\s+(?:adults?|people|visitors?|guests?)\s+free\b|"
    r"general\s+admission\s+pass\s+to\s+the\s+state\s+parks|"
    r"parkspass\s+is\s+valid|free\s+access|"
    r"(?:pass\s+)?allows?\s+\d+\s+cars?\s+(?:and\s+passengers\s+)?(?:into|to)\s+(?:the\s+)?(?:state\s+park|beach)|"
    r"allow(?:s)?\s+\d+\s+cars?\s+(?:and\s+passengers\s+)?(?:into|to)|"
    r"(?:free\s+)?admission\s+for\s+a\s+family|"
    r"one\s+carload|allows?\s+\d+\s+carloads?"
    r")\b",
    re.I,
)
_FREE_ANY = re.compile(
    r"\b(free|complimentary)\b", re.I,
)

_PERCENT = re.compile(r"(\d{1,3})\s*%\s*(?:off|discount(?:ed)?)?", re.I)
_HALF = re.compile(r"\b(half[\s-]?priced?|half off|half-?price(?:d)?\s+admission|1/2\s+(?:price|off)|1/2-?price|half\s+the\s+regular\s+admission)\b", re.I)
_DOLLAR_OFF = re.compile(r"\$\s*(\d+(?:\.\d+)?)\s*(?:-)?\s*off(?:\s+each|\s+per\s+person|\s+per\s+ticket)?", re.I)
_DOLLAR_OFF_ALT = re.compile(r"(?:savings\s+of\s+)\$\s*(\d+(?:\.\d+)?)\s*off?", re.I)

# per-person price expressions
_PER_PERSON = re.compile(
    r"\$\s*(\d+(?:\.\d+)?)\s*(?:/|\s+per\s+|\s+a\s+|\s+)\s*(?:admission|person|ticket|each|adult|child|senior|youth|student|visitor|/?\s*each|/visitor|co-?pay)\b",
    re.I,
)
# "$5 each" style
_DOLLAR_EACH = re.compile(r"\$\s*(\d+(?:\.\d+)?)\s+each\b", re.I)
# "$2 per visitor over the age of N"
_PER_VISITOR = re.compile(r"\$\s*(\d+(?:\.\d+)?)\s+per\s+(?:visitor|person|guest|adult|ticket|admission)", re.I)
# "for free" — admitted free without explicit "free admission"
_FOR_FREE = re.compile(r"\bfor\s+free\b|\bfree\s+of\s+charge\b|\bguests?\s+free\b|\bpeople\s+(?:in\s+)?for\s+free\b|\badmits\s+\d+\s+(?:people|guests?|visitors?)\s+for\s+free\b", re.I)
# Less constrained per-person price (used inside an audience clause)
_PRICE_ONLY = re.compile(r"\$\s*(\d+(?:\.\d+)?)\b")

# Audience-specific clauses
_ADULT_PRICE = re.compile(
    r"(?:admission(?:\s+costs?)?\s+(?:with\s+the\s+pass\s+)?are?\s+)?"
    r"\$\s*(\d+(?:\.\d+)?)\s*(?:/|\s+per\s+|\s+each\s+for\s+|\s+for\s+|\s+a\s+|\s+charge\s+per\s+|\s+co-?pay\s+(?:for|per)\s+|\s+)?\s*adult",
    re.I,
)
_ADULT_PRICE_REV = re.compile(
    r"\badult(?:s|s/seniors?)?(?:\s+admission)?(?:\s+is\s+reduced\s+to)?[:\s]*(?:tickets?\s+)?(?:are\s+)?\$\s*(\d+(?:\.\d+)?)",
    re.I,
)
_ADULT_PRICE_FOR = re.compile(
    r"\$\s*(\d+(?:\.\d+)?)\s+for\s+(?:\w+\s+)?\(?(?:\d+|two|three|four|five|six)\)?\s+adults?",
    re.I,
)
_CHILD_PRICE = re.compile(
    r"\$\s*(\d+(?:\.\d+)?)\s*(?:/|\s+per\s+|\s+each\s+for\s+|\s+for\s+|\s+a\s+|\s+charge\s+per\s+|\s+co-?pay\s+(?:for|per)\s+|\s+)?\s*child(?:ren)?",
    re.I,
)
_CHILD_PRICE_REV = re.compile(
    r"\bchild(?:ren)?(?:\s+admission)?(?:\s+to)?[:\s]*(?:are\s+)?\$\s*(\d+(?:\.\d+)?)",
    re.I,
)
_CHILDREN_FREE = re.compile(
    r"\b(?:admission\s+is\s+)?free\s+(?:to\s+|for\s+|to anyone\s+)?(?:children|kids|child(?:ren)?(?:\s+ages?\s+\d+(?:\s*(?:-|to|and under)\s*\d+)?)?|anyone\s+\d+\s+and\s+under|kids\s+\d+\s+and\s+under|child(?:ren)?\s+under\s+\d+)",
    re.I,
)
_CHILD_UNDER = re.compile(
    r"(?:child(?:ren)?|kids?|anyone)\s+(?:ages?\s+)?(?:under|below)\s+(\d+)(?:\s+(?:are\s+|is\s+)?free)?",
    re.I,
)
_CHILD_AND_UNDER = re.compile(
    r"(?:child(?:ren)?|kids?|anyone)\s+(\d+)\s+(?:years?\s+)?and\s+under",
    re.I,
)

_BOGO = re.compile(
    r"\b(2[ \-]?for[ \-]?1|two[ \-]?for[ \-]?one|buy\s+one\s+get\s+one)\b",
    re.I,
)
_DISCOUNT_GENERIC = re.compile(
    r"\b(discount(?:ed)?\s+admission|discount(?:ed)?\s+ticket(?:s)?|discounted\s+price|"
    r"discount(?:ed)?\s+rate|discounted\s+library\s+(?:pass\s+)?(?:price|rate)|"
    r"discount(?:ed)?\s+library\s+price|go\s+pass\s+coupon|discount)\b",
    re.I,
)

# Trustees "GO Pass" / Family-Membership-equivalent benefit. The text never
# states a flat dollar figure or percentage: the holder pays the reduced
# Trustees *Family Level membership* admission price (free at some sites,
# reduced at others). The honest mapping is a generic "discount" — we do NOT
# fabricate "FREE" because the text says "free OR reduced" / "equivalent to a
# Family Membership admission price".
_TRUSTEES_GO_PASS = re.compile(
    r"("
    r"equivalent to (?:a |the )?(?:admission benefit of (?:a |the )?)?trustees? family (?:level )?membership"
    r"|admission benefit of (?:a |the )?trustees? family (?:level )?membership"
    r"|trustees? family (?:level )?membership admission (?:price|rate)"
    r"|family (?:level )?(?:membership )?admission (?:price|rate)s?"
    r"|at family membership rates?"
    r"|entry at family membership rates?"
    r"|free or reduced admission"
    r"|go ?pass(?:es)? (?:are|is) (?:valid for admission|good for admission)"
    r")",
    re.I,
)
# "free or reduced admission" is explicitly ambiguous (NOT a guaranteed FREE);
# it must route to the Trustees discount branch, never to the plain-FREE one.
_FREE_OR_REDUCED = re.compile(r"\bfree\s+or\s+reduced\b", re.I)

# "Pass benefits:" / "Pass provides ..." markers used by libcal entries that
# bury the actual benefit clause after a long museum description + address.
# We isolate the clause so FREE / discount detection isn't crowded out of the
# 4-sentence headline window by the boilerplate prefix.
_BENEFIT_MARKER = re.compile(
    r"(?:pass\s+benefits?\s*:|this\s+pass\s+(?:will\s+)?provides?|pass\s+provides?|"
    r"this\s+pass\s+(?:will\s+)?admits?|pass\s+admission\s+is|coupon\s+(?:code\s+)?(?:covers|good\s+for|allows))"
    r"\s*",
    re.I,
)

# "Free admission for up to 4", "Admits up to 9 for free", "Free <Name>
# admission", "Free Lecture Series Pass", "Free ... family admission",
# "covers the cost of N tickets" (== free), "free or reduced ... free".
_FREE_BENEFIT = re.compile(
    r"\b("
    r"free\s+admission\s+for\s+(?:up\s+to\s+)?\d+"
    r"|admits?\s+(?:up\s+to\s+)?\d+\s+(?:\([^)]*\)\s+)?for\s+free"
    r"|free\s+(?:general\s+)?admission"
    r"|free\s+(?:\w+\s+){0,3}admission"
    r"|free\s+(?:lecture|admission|entry|family\s+admission|guest\s+admission)"
    r"|free\s+(?:\w+\s+){0,3}pass\b"
    r"|covers?\s+the\s+cost\s+of"
    r")\b",
    re.I,
)

# "$5 for four (4) adults" — reduced per-adult price stated as a lump for N.
_PRICE_FOR_N_ADULTS = re.compile(
    r"\$\s*(\d+(?:\.\d+)?)\s+for\s+(?:\w+\s+)?\(?(?:\d+|two|three|four|five|six)\)?\s+adults?",
    re.I,
)
# "Each visitor will be charged $2.00" — per-person price, reversed phrasing.
_CHARGED_PER_VISITOR = re.compile(
    r"\beach\s+(?:visitor|person|guest|patron|adult)\s+(?:will\s+be\s+)?charged\s+\$\s*(\d+(?:\.\d+)?)",
    re.I,
)
# Reversed-currency dollar-off, e.g. "50$ off regular admission".
_DOLLAR_OFF_REV = re.compile(r"\b(\d+(?:\.\d+)?)\s*\$\s*off\b", re.I)


@dataclass
class Policy:
    audience: str = "Everyone"
    form: str = "discount"
    value: float | int | None = None
    count: int | None = None
    age_range: dict[str, int] | None = None
    source_phrase: str = ""

    def as_dict(self) -> dict[str, Any]:
        # Match the field order produced by the LLM outputs.
        return {
            "audience": self.audience,
            "form": self.form,
            "value": self.value,
            "count": self.count,
            "age_range": self.age_range,
            "source_phrase": self.source_phrase,
        }


def _normalize_value(v: float) -> float | int:
    """Return int if value is whole, else float."""
    if v == int(v):
        return int(v)
    return v


def _detect_bogo(text: str) -> bool:
    return bool(_BOGO.search(text))


def _detect_free_headline(text: str) -> bool:
    # FREE wins if it appears in the leading content BEFORE any
    # competing $ figure or percent-off / discount expression.
    # We scan up to the first 4 sentences so phrases like
    # "Print from home pass." don't block the next "Pass admits 2 for free."
    text = text.strip()
    sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
    scanned = ""
    for s in sentences[:4]:
        if not s:
            continue
        scanned += " " + s
        # Headline competition: if we've already encountered a $ figure or
        # a percent-off / discount expression in the leading text, FREE
        # cannot be the headline.
        if "$" in scanned:
            return False
        if _PERCENT.search(scanned) or _HALF.search(scanned):
            return False
        if _FREE_HEADLINE.search(scanned) or _FOR_FREE.search(scanned):
            return True
    return False


_DCR_PARKING_HINT = re.compile(
    r"\b(dcr\s+parks?\s+pass|state\s+park(?:s)?|parking\s+(?:access|pass|fee|at)|unlimited\s+parking|day-use\s+parking)\b",
    re.I,
)


def _detect_dcr_free(text: str) -> bool:
    """DCR / Mass-State-Parks parking passes are FREE-by-default."""
    return bool(_DCR_PARKING_HINT.search(text))


def _build_summary(form: str, value: float | int | None, first_phrase: str,
                   has_count_only: bool = False) -> str:
    if form == "free":
        if re.search(r"\bparking\b", first_phrase, re.I):
            return "FREE parking"
        return "FREE"
    if form == "percent-off" and value is not None:
        return f"{_normalize_value(value)}% off"
    if form == "dollar-off" and value is not None:
        return f"${_normalize_value(value)} off"
    if form == "per-person-price" and value is not None:
        return f"${_normalize_value(value)}/person"
    if form == "bogo":
        return "BOGO"
    # Generic discount form: use "Discount" when assabet pattern produced a
    # count, else lower-case "discount" (libcal-style).
    if has_count_only:
        return "Discount"
    return "discount"


# ---------------------------------------------------------------------------
# Restrictions
# ---------------------------------------------------------------------------

_BLACKOUT_MONTHS = re.compile(
    r"\b(?:not valid|closed|blackout)[^.]*\b(january|february|march|april|may|june|july|august|september|october|november|december)\b",
    re.I,
)
_WEEKDAYS_ONLY = re.compile(
    r"\b(?:only\s+)?(?:valid\s+)?(?:mon(?:day)?(?:s)?\s*(?:-|to|through|–)\s*fri(?:day)?(?:s)?|weekdays only)\b",
    re.I,
)
_ADVANCE_BOOKING = re.compile(
    r"\b(advance\s+reservation|advanced?\s+ticket\s+purchase|advance\s+booking|reservation\s+required)\b",
    re.I,
)

_MONTH_TO_INT = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}


def extract_restrictions(text: str) -> dict[str, Any] | None:
    t = _clean(text)
    out: dict[str, Any] = {
        "blackout": [],
        "blackout_recurring": [],
        "weekdays_only": False,
        "seasonal": None,
        "advance_booking_required": False,
        "advance_booking_hours": None,
    }
    any_hit = False
    m = _BLACKOUT_MONTHS.search(t)
    if m:
        out["blackout"].append({"month": _MONTH_TO_INT[m.group(1).lower()], "day": None})
        any_hit = True
    if _WEEKDAYS_ONLY.search(t):
        out["weekdays_only"] = True
        any_hit = True
    if _ADVANCE_BOOKING.search(t):
        out["advance_booking_required"] = True
        any_hit = True
    return out if any_hit else None


# --- residency restriction (the real booking filter) -------------------------
# Mostly NOT stated in catalog text — the platform enforces it at reservation
# time against the ZIP on the card. We only emit a restriction when the text
# EXPLICITLY ties a residency requirement to reserving/using THIS pass. The
# distinction from a museum's own admission policy ("residents of Salem are
# admitted free") is the pass/reserve/use cue; without it we stay unknown.

# Town-scope: "Only <Town> residents may reserve/use this pass".
_RES_TOWN = re.compile(
    r"\bonly\s+([A-Z][a-zA-Z]+)\s+residents?\s+(?:may|can)\s+"
    r"(?:reserve|use|borrow|check\s*out|request)\b",
    re.I,
)
# MA-scope tied to the pass: "must be a Massachusetts resident to use this pass",
# "member/each of the party must be a MA resident", "visitors must be MA residents
# to use this pass".
_RES_MA = re.compile(
    r"\b(?:must\s+be\s+(?:a\s+)?|each\s+of\s+the\s+party\s+must\s+be\s+(?:a\s+)?|"
    r"(?:member|one\s+member)\s+of\s+the\s+(?:party|group)\s+must\s+be\s+(?:a\s+)?|"
    r"visitors?\s+must\s+be\s+)"
    r"(?:massachusetts|mass\.?|MA)\s+residents?\b",
    re.I,
)


def extract_residency_restriction(text: str) -> dict[str, Any] | None:
    """Detect an explicit pass-reservation residency requirement in the text.

    Returns a dict with restricted/scope/source/evidence, or None when the text
    states nothing (the caller then leaves it ``unknown`` — NOT ``no``, because
    silence in catalog text does not mean the pass is open; the platform may
    still enforce residency at booking time).
    """
    t = _clean(text)
    m = _RES_TOWN.search(t)
    if m:
        a = max(0, m.start() - 10)
        b = min(len(t), m.end() + 50)
        return {"restricted": "yes", "scope": "town",
                "source": "catalog_text", "evidence": t[a:b].strip()}
    m = _RES_MA.search(t)
    if m:
        a = max(0, m.start() - 20)
        b = min(len(t), m.end() + 40)
        return {"restricted": "yes", "scope": "ma",
                "source": "catalog_text", "evidence": t[a:b].strip()}
    return None


# ---------------------------------------------------------------------------
# Main extractor
# ---------------------------------------------------------------------------


def extract_coupon(
    library_id: str,
    attraction_slug: str,
    benefit_text: str,
    source_phrases: list[str] | None = None,
    platform: str = "assabet",
) -> dict[str, Any]:
    """Run the deterministic coupon extractor, then attach any explicit
    residency restriction found in the same benefit text.

    Returns a dict with either ``status=ok`` + ``extracted`` or ``status=failed``.
    ``extracted.residency_restriction`` is included only when the text states an
    explicit pass-reservation residency requirement; otherwise it is omitted and
    the build leaves the pass at ``residency_restriction = unknown``.
    """
    result = _extract_coupon_inner(
        library_id, attraction_slug, benefit_text, source_phrases, platform
    )
    if result.get("status") == "ok":
        joined = _join_source(source_phrases, (benefit_text or "").strip())
        rr = extract_residency_restriction(joined)
        if rr is not None:
            result["extracted"]["residency_restriction"] = rr
    return result


def _extract_coupon_inner(
    library_id: str,
    attraction_slug: str,
    benefit_text: str,
    source_phrases: list[str] | None = None,
    platform: str = "assabet",
) -> dict[str, Any]:
    raw_text = (benefit_text or "").strip()
    if not raw_text:
        return {"status": "failed", "error": "no benefit text"}

    # Navigation-only short circuit.
    clean_one_line = _clean(raw_text)
    for pat in _NAV_ONLY_PATTERNS:
        if pat.match(clean_one_line):
            return {"status": "failed", "error": "no benefit text available"}

    text_joined = _join_source(source_phrases, raw_text)
    text_for_match = _strip_negative_ctx(text_joined)

    capacity = extract_capacity(text_joined)
    pass_form = classify_pass_form(text_joined, slug=attraction_slug, platform=platform)
    source_phrase_block = _clean(raw_text)
    base_source = _phrase_window(text_joined, 280)

    # ---- BOGO -----------------------------------------------------------
    if _detect_bogo(text_joined):
        policy = Policy(
            audience="Everyone", form="bogo", value=None,
            count=capacity.n, age_range=None,
            source_phrase=base_source,
        )
        summary = "BOGO"
        return _ok(pass_form, capacity, [policy], summary,
                   source_phrase_block, extract_restrictions(text_joined))

    # ---- FREE (headline-wins) ------------------------------------------
    if _detect_free_headline(text_for_match):
        # If parking AND libcal, summary uses "FREE parking" (libcal-only
        # convention from the upstream extractors; assabet always says
        # just "FREE" even for parking benefits).
        first = re.split(r"(?<=[.!?])\s+", text_joined.strip(), maxsplit=1)[0]
        is_parking = bool(re.search(r"\bparking\b", first, re.I))
        policy = Policy(
            audience="Everyone", form="free", value=0,
            count=capacity.n, age_range=None,
            source_phrase=base_source,
        )
        summary = "FREE parking" if (is_parking and platform == "libcal") else "FREE"
        return _ok(pass_form, capacity, [policy], summary,
                   source_phrase_block, extract_restrictions(text_joined))

    # ---- Trustees GO Pass / Family-Membership-equivalent ----------------
    # Honest mapping: the pass entitles the holder to the Trustees Family Level
    # *admission price* (free at some sites, reduced at others). Because the
    # text says "free OR reduced" / "equivalent to a Family Membership price"
    # rather than a flat figure, we emit a generic "discount" with a count of
    # admitted people, never a fabricated "FREE" / dollar / percent value.
    if _TRUSTEES_GO_PASS.search(text_for_match):
        policy = Policy(
            audience="Everyone", form="discount", value=None,
            count=capacity.n, age_range=None,
            source_phrase=base_source,
        )
        has_count = capacity.n is not None
        summary = _build_summary("discount", None, text_joined, has_count_only=has_count)
        return _ok(pass_form, capacity, [policy], summary,
                   source_phrase_block, extract_restrictions(text_joined))

    # ---- FREE (benefit-clause, scanned anywhere in text) ----------------
    # libcal entries bury "Pass benefits: Free admission for up to 4" after a
    # long museum description; the 4-sentence headline window above misses it.
    # Here we accept an explicit free-admission benefit phrase regardless of
    # position, but only when no competing $ / % figure precedes it.
    if _FREE_BENEFIT.search(text_for_match) and not (
        _FREE_OR_REDUCED.search(text_for_match)
        or _PERCENT.search(text_for_match)
        or _HALF.search(text_for_match)
        or _DOLLAR_OFF.search(text_for_match)
        or _PER_PERSON.search(text_for_match)
        or _DOLLAR_EACH.search(text_for_match)
        or _PER_VISITOR.search(text_for_match)
        or _CHARGED_PER_VISITOR.search(text_for_match)
    ):
        first = re.split(r"(?<=[.!?])\s+", text_joined.strip(), maxsplit=1)[0]
        is_parking = bool(re.search(r"\bparking\b", first, re.I))
        policy = Policy(
            audience="Everyone", form="free", value=0,
            count=capacity.n, age_range=None,
            source_phrase=base_source,
        )
        summary = "FREE parking" if (is_parking and platform == "libcal") else "FREE"
        return _ok(pass_form, capacity, [policy], summary,
                   source_phrase_block, extract_restrictions(text_joined))

    # NOTE: we intentionally do NOT auto-emit FREE for DCR / state-park parking
    # passes that merely describe vehicle-display logistics (e.g. boxford ISGM:
    # "displayed in your vehicle ... where daily parking fees are charged").
    # The free-ness there is domain inference, not literal text, so per the
    # honesty rule those stay failed unless the text says "free parking" /
    # "1 vehicle for free" (handled by the FREE headline branch above).

    # ---- Adult + child two-tier per-person prices ----------------------
    adult_m = (
        _ADULT_PRICE.search(text_for_match)
        or _ADULT_PRICE_REV.search(text_for_match)
        or _ADULT_PRICE_FOR.search(text_for_match)
    )
    child_m = _CHILD_PRICE.search(text_for_match) or _CHILD_PRICE_REV.search(text_for_match)
    if adult_m and child_m:
        adult_v = float(adult_m.group(1))
        child_v = float(child_m.group(1))
        policies = [
            Policy(
                audience="adults", form="per-person-price",
                value=_normalize_value(adult_v), count=None,
                age_range={"min": 18, "max": 200},
                source_phrase=base_source,
            ),
            Policy(
                audience="children", form="per-person-price",
                value=_normalize_value(child_v), count=None,
                age_range=None,
                source_phrase=base_source,
            ),
        ]
        summary = f"${_normalize_value(adult_v)}/person"
        return _ok(pass_form, capacity, policies, summary,
                   source_phrase_block, extract_restrictions(text_joined))

    # ---- Percent-off (or half-price) -----------------------------------
    pct_m = _PERCENT.search(text_for_match)
    half_m = _HALF.search(text_for_match)
    if pct_m or half_m:
        pct = int(pct_m.group(1)) if pct_m else 50
        primary = Policy(
            audience="Everyone", form="percent-off", value=pct,
            count=capacity.n, age_range=None,
            source_phrase=base_source,
        )
        policies = [primary]
        # Secondary children policy?
        cm = _CHILD_PRICE.search(text_for_match) or _CHILD_PRICE_REV.search(text_for_match)
        if cm:
            policies.append(Policy(
                audience="children", form="per-person-price",
                value=_normalize_value(float(cm.group(1))), count=None,
                age_range=None,
                source_phrase=base_source,
            ))
        summary = f"{pct}% off"
        return _ok(pass_form, capacity, policies, summary,
                   source_phrase_block, extract_restrictions(text_joined))

    # ---- Dollar-off ----------------------------------------------------
    d_m = (
        _DOLLAR_OFF.search(text_for_match)
        or _DOLLAR_OFF_ALT.search(text_for_match)
        or _DOLLAR_OFF_REV.search(text_for_match)
    )
    if d_m:
        v = float(d_m.group(1))
        policy = Policy(
            audience="Everyone", form="dollar-off",
            value=_normalize_value(v), count=capacity.n,
            age_range=None,
            source_phrase=base_source,
        )
        summary = f"${_normalize_value(v)} off"
        return _ok(pass_form, capacity, [policy], summary,
                   source_phrase_block, extract_restrictions(text_joined))

    # ---- Plain per-person-price ---------------------------------------
    pp_m = (
        _PER_PERSON.search(text_for_match)
        or _DOLLAR_EACH.search(text_for_match)
        or _PER_VISITOR.search(text_for_match)
        or _CHARGED_PER_VISITOR.search(text_for_match)
        or _PRICE_FOR_N_ADULTS.search(text_for_match)
    )
    if pp_m:
        v = float(pp_m.group(1))
        policy = Policy(
            audience="Everyone", form="per-person-price",
            value=_normalize_value(v), count=capacity.n,
            age_range=None,
            source_phrase=base_source,
        )
        summary = f"${_normalize_value(v)}/person"
        return _ok(pass_form, capacity, [policy], summary,
                   source_phrase_block, extract_restrictions(text_joined))

    # ---- Generic discount ---------------------------------------------
    if _DISCOUNT_GENERIC.search(text_for_match):
        has_count = capacity.n is not None
        policy = Policy(
            audience="Everyone", form="discount", value=None,
            count=capacity.n, age_range=None,
            source_phrase=base_source,
        )
        summary = _build_summary("discount", None, text_joined, has_count_only=has_count)
        return _ok(pass_form, capacity, [policy], summary,
                   source_phrase_block, extract_restrictions(text_joined))

    return {"status": "failed", "error": "unparsed benefit"}


def _ok(pass_form: str, capacity: Capacity, policies: list[Policy],
        summary: str, source_block: str,
        restrictions: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "status": "ok",
        "extracted": {
            "pass_form": pass_form,
            "coupon": {
                "capacity": capacity.as_dict(),
                "audience_policies": [p.as_dict() for p in policies],
                "summary": summary,
                "source_phrase_block": source_block,
            },
            "restrictions": restrictions,
        },
    }
