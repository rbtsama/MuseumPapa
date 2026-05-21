"""Regex classifier for library-card eligibility + pass-pickup policy.

Design goal (honesty-first): only emit a non-``unknown`` value when the scraped
text contains a genuine eligibility *statement*. We anchor every pattern so that
incidental words ("Apply to be the next Kid Librarian", "Hoopla now available to
Boxford Residents!", a program blurb that merely mentions "residents", a bare
"work" in a job posting) do NOT trigger a classification. Ambiguous cases fall
back to ``UNKNOWN`` and are handled by LLM dispatch + audit overrides.
"""
from __future__ import annotations
import re
from malibbene.schema.library import CardEligibility, PassPickupPolicy

# --- MA-resident -------------------------------------------------------------
# "any Massachusetts resident", "all Massachusetts residents", "residents of the
# Commonwealth", "resident of Massachusetts", "Massachusetts residency is required".
_MA_RESIDENT = re.compile(
    r"\b(?:massachusetts|mass\.?)\s+residen"                        # MA resident / residency
    r"|\bresidents?\s+of\s+(?:the\s+)?(?:commonwealth|massachusetts)\b"
    r"|\bresident\s+of\s+(?:the\s+state\s+of\s+)?massachusetts\b",
    re.I,
)

# --- open access: "Anyone is eligible for a library card" / "Anyone can get a card"
# Means anyone (any MA resident, in practice) may register — classified MA_RESIDENT.
_OPEN_ANYONE = re.compile(
    r"\banyone\s+(?:is\s+eligible|can\s+(?:get|apply|register)|may\s+(?:apply|register|get))"
    r"[^.]{0,60}(?:card|library)"
    r"|\b(?:any|all)\s+residents?\s+(?:may|can)\s+(?:register|apply|use\s+(?:any|the))",
    re.I,
)

# --- "live, work, or attend school in <Town>" / "own property in <Town>" ------
# Requires TWO of the live/work/school/own-property predicates close together so
# a lone "work" elsewhere on the page cannot match (the real idiom always lists
# at least two: "live, work, or attend school in ...").
_TOWN_OR_WORKS = re.compile(
    r"\b(?:live|reside|work|own\s+property|attend\s+school|go\s+to\s+school|"
    r"are\s+employed|own\s+a\s+(?:home|business))\b"
    r"[^.]{0,80}\b(?:work|live|reside|attend\s+school|go\s+to\s+school|"
    r"own\s+property|own\s+a\s+(?:home|business)|are\s+employed)\b",
    re.I,
)

# --- town-resident only ------------------------------------------------------
# "Wakefield residents only", "<Town> residents may register", "card is available
# to all <Town> residents", "residents of <Town> [proper/may/...]", "must reside
# in <Town>". Every branch carries a card / register / borrow cue (or the explicit
# "residents only" idiom) so that service-announcement prose like "Hoopla is now
# available to Boxford Residents!" or "residents of all ages" does NOT match.
_TOWN_RESIDENT = re.compile(
    # "...card(s)/borrow/register/apply/eligible... <Town> residents only" — the
    # "residents only" idiom must sit in a card-registration context (within the
    # same sentence) so a streaming-service caveat ("...with your library card
    # number. Sudbury residents only.") does NOT match across the sentence break.
    r"\b(?:card|cards|borrow|register|registration|apply|eligible|available)\b"
    r"[^.!?\n]{0,70}\bresidents?\s+only\b"
    r"|\b[A-Z][a-zA-Z]+\s+residents?\s+may\s+(?:register|apply|borrow|get)\b"
    r"|\b(?:library\s+)?card\s+(?:is\s+)?available\s+(?:only\s+)?to\s+(?:all\s+)?"
    r"(?:[A-Z][a-zA-Z]+\s+){1,2}residents?\b"
    r"|\bresidents?\s+of\s+[A-Z][a-zA-Z]+\s+(?:proper\b|may\s+(?:register|apply|borrow)\b)"
    r"|\bmust\s+(?:be\s+a\s+resident\s+of|reside\s+in|live\s+in)\s+[A-Z][a-zA-Z]+",
    re.I,
)

# --- network card ------------------------------------------------------------
# "NOBLE network card", "valid library card from ... NOBLE/Minuteman/MVLC/OCLN".
# Anchored to a "valid|use|your ... card from/at <network>" idiom so a bare menu
# link like "MVLC & BPL E-cards" does NOT match.
_NETWORK = re.compile(
    r"\b(?:valid|use\s+your|your)\s+(?:library\s+)?card\s+(?:from|at|in)\b[^.]{0,40}"
    r"\b(?:NOBLE|Minuteman|MVLC|OCLN|Merrimack\s+Valley\s+Library\s+Consortium|"
    r"library\s+network|consortium)\b"
    r"|\b(?:NOBLE|Minuteman|MVLC|OCLN|Merrimack\s+Valley\s+Library\s+Consortium)\b"
    r"\s+(?:network\s+)?card\b"
    r"|\b(?:NOBLE|Minuteman)\s+(?:library\s+)?network\b[^.]{0,30}\bcard\b",
    re.I,
)

# --- pass-pickup specific ----------------------------------------------------
_WALKIN = re.compile(r"non.?residents?.*walk.?in", re.I)
_TOWN_CARDHOLDER = re.compile(
    r"(?:holding|issued\s+by|patrons\s+of|patrons\s+holding|reserved\s+for\s+patrons)"
    r"\s+(?:a\s+)?(?:[A-Z][a-z]+\s+)?"
    r"(?:this\s+library|our\s+library|the\s+[A-Z][a-z]+\s+library|[A-Z][a-z]+\s+library)"
    r"\s*(?:card)?"
    r"|\bfor\s+[A-Z][a-z]+\s+(?:library\s+)?cardholders?\b",
    re.I,
)


def _span_phrase(text: str, m: "re.Match") -> str:
    """Return the matched eligibility statement with a little context, cleaned."""
    a = max(0, m.start() - 30)
    b = min(len(text), m.end() + 60)
    return re.sub(r"\s+", " ", text[a:b]).strip()


def classify_card_eligibility_with_phrase(text: str) -> tuple[CardEligibility, str | None]:
    """Like classify_card_eligibility but also returns the verbatim matched
    phrase (provenance). Every non-UNKNOWN value therefore carries the exact
    text that justifies it — the honesty invariant the audit relies on. UNKNOWN
    returns (UNKNOWN, None)."""
    if not text:
        return CardEligibility.UNKNOWN, None
    # Order: broadest legitimate access first, then narrower scopes.
    m = _MA_RESIDENT.search(text) or _OPEN_ANYONE.search(text)
    if m:
        return CardEligibility.MA_RESIDENT, _span_phrase(text, m)
    m = _TOWN_OR_WORKS.search(text)
    if m:
        return CardEligibility.TOWN_OR_WORKS, _span_phrase(text, m)
    m = _TOWN_RESIDENT.search(text)
    if m:
        return CardEligibility.TOWN_RESIDENT, _span_phrase(text, m)
    m = _NETWORK.search(text)
    if m:
        return CardEligibility.NETWORK, _span_phrase(text, m)
    return CardEligibility.UNKNOWN, None


def classify_card_eligibility(text: str) -> CardEligibility:
    return classify_card_eligibility_with_phrase(text)[0]


# A residency restriction only counts as a *pass-pickup* policy when it sits in
# the same sentence as a pass / reservation cue. Pass-page text is dominated by
# individual museum blurbs (e.g. "Harvard Museums ... are free to Massachusetts
# residents every Sunday morning") that describe the MUSEUM's own admission rules,
# not who at the library may reserve the pass — those must NOT classify pickup.
_PASS_RESIDENCY_SENTENCE = re.compile(
    r"[^.!?\n]*\b(?:pass|passes|reserve|reservation|check\s+out|pick\s+up|borrow)\b"
    r"[^.!?\n]*\b(?:(?:massachusetts|mass\.?)\s+residents?|[A-Z][a-zA-Z]+\s+residents?\s+only|"
    r"residents?\s+only|residents?\s+of\s+(?:the\s+)?(?:commonwealth|massachusetts|[A-Z][a-zA-Z]+))\b"
    r"|[^.!?\n]*\b(?:(?:massachusetts|mass\.?)\s+residents?|[A-Z][a-zA-Z]+\s+residents?\s+only|"
    r"residents?\s+only)\b"
    r"[^.!?\n]*\b(?:pass|passes|reserve|reservation|check\s+out|pick\s+up|borrow)\b",
    re.I,
)


def classify_pass_pickup(text: str) -> PassPickupPolicy:
    if not text:
        return PassPickupPolicy.UNKNOWN
    if _WALKIN.search(text):
        return PassPickupPolicy.WALKIN_FOR_NONRESIDENTS
    if _TOWN_CARDHOLDER.search(text):
        return PassPickupPolicy.TOWN_CARDHOLDER_ONLY
    # Residency-scoped pickup only when tied to a pass/reservation cue.
    sent = _PASS_RESIDENCY_SENTENCE.search(text)
    if sent:
        frag = sent.group(0)
        if _MA_RESIDENT.search(frag):
            return PassPickupPolicy.MA_RESIDENT
        if _TOWN_RESIDENT.search(frag) or re.search(r"\bresidents?\s+only\b", frag, re.I):
            return PassPickupPolicy.TOWN_RESIDENT
    if _NETWORK.search(text):
        return PassPickupPolicy.NETWORK
    return PassPickupPolicy.UNKNOWN
