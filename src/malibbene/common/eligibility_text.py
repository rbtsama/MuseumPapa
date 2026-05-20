"""Lightweight regex classifier; complex cases go to LLM dispatch + audit overrides."""
from __future__ import annotations
import re
from malibbene.schema.library import CardEligibility, PassPickupPolicy

_WALKIN = re.compile(r"non.?residents?.*walk.?in", re.I)
_TOWN_CARDHOLDER = re.compile(r"(holding|issued by|patrons of|patrons holding)\s+(a\s+)?([A-Z][a-z]+\s+)?(this library|our library|the [A-Z][a-z]+ library|[A-Z][a-z]+ library)\s*(card)?", re.I)
_TOWN_ONLY = re.compile(r"\b([A-Z][a-z]+)\s+residents?\s+only\b|\bresidents?\s+only\b", re.I)
_TOWN_OR_WORKS = re.compile(r"\b(live|work|attend school)\b", re.I)
_MA_RESIDENT = re.compile(r"\bMassachusetts\s+resident", re.I)
_NETWORK = re.compile(r"\b(NOBLE|Minuteman|MVLC|OCLN|consortium|network)\s+card", re.I)

def classify_card_eligibility(text: str) -> CardEligibility:
    if not text:
        return CardEligibility.UNKNOWN
    if _MA_RESIDENT.search(text):
        return CardEligibility.MA_RESIDENT
    if _TOWN_OR_WORKS.search(text):
        return CardEligibility.TOWN_OR_WORKS
    if _TOWN_ONLY.search(text):
        return CardEligibility.TOWN_RESIDENT
    if _NETWORK.search(text):
        return CardEligibility.NETWORK
    return CardEligibility.UNKNOWN

def classify_pass_pickup(text: str) -> PassPickupPolicy:
    if not text:
        return PassPickupPolicy.UNKNOWN
    if _WALKIN.search(text):
        return PassPickupPolicy.WALKIN_FOR_NONRESIDENTS
    if _TOWN_CARDHOLDER.search(text):
        return PassPickupPolicy.TOWN_CARDHOLDER_ONLY
    if _TOWN_ONLY.search(text):
        return PassPickupPolicy.TOWN_RESIDENT
    if _MA_RESIDENT.search(text):
        return PassPickupPolicy.MA_RESIDENT
    if _NETWORK.search(text):
        return PassPickupPolicy.NETWORK
    return PassPickupPolicy.UNKNOWN
