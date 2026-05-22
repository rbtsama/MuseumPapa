"""Canonical slug mapping for attraction entities.

Some attractions are referenced by multiple slugs across platforms (Assabet vs
LibCal vs MuseumKey) and across pass-form variants (`-e-coupon`,
`-physical-pass`, ...). This module collapses those duplicates onto a single
canonical winner so downstream consumers only ever see canonical slugs.

`canonical(slug)` resolves in this order (honesty: only collapse clearly-same
entities, never merge distinct ones):

  0. Hand map (`LEGACY_TO_CANONICAL`) — exact spelling variants that the legacy
     archive does NOT already cover. Checked FIRST so deliberate
     disambiguations (e.g. the Boston Harbor *ferry* vs the *islands* park)
     win over generic suffix stripping.
  1. Suffix strip — drop a pass-form / variant suffix (`-e-coupon`, ...) ONLY
     when the stripped base resolves to a known canonical slug. Re-run the hand
     map + legacy map on the stripped base.
  2. Legacy auto map — `{legacy_slug -> canonical_slug}` built from the legacy
     attractions archive (each record's `slug` is canonical; every entry in its
     `legacy_slugs` maps to it).
  3. Otherwise the slug is returned unchanged (it becomes its own attraction —
     the honest default for anything we are unsure about).
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

_LEGACY_ATTRACTIONS = (
    Path(__file__).resolve().parents[3]
    / "data" / "_legacy" / "2026-05-20" / "attractions.json"
)

# Pass-form / variant suffixes. Longest-first so e.g. `-digital-coupon-pass`
# is tried before `-digital`/`-pass`. Stripped ONLY when the base resolves.
_SUFFIXES = [
    "-digital-coupon-pass",
    "-coupon-code",
    "-promo-code",
    "-physical-pass",
    "-digital-pass",
    "-e-coupon",
    "-ecoupon",
    "-e-ticket",
    "-physical",
    "-digital",
    "-seasonal",
    "-ferry",
]
_SUFFIX_RE = re.compile(r"(" + "|".join(re.escape(s) for s in _SUFFIXES) + r")$")

# Hand-verified spelling variants NOT covered by the legacy archive's own
# `legacy_slugs`. Every entry here is a deliberate "these two slugs are the
# SAME real-world entity" assertion — see the report for verification.
LEGACY_TO_CANONICAL: dict[str, str] = {
    # --- Boston Harbor: ferry must NOT collapse onto the islands park.
    # The legacy archive keeps `boston-harbor-island-ferry` and
    # `boston-harbor-islands` as two distinct entities, so we redirect the
    # `-islands-ferry` spelling to the ferry (checked before suffix-strip,
    # which would otherwise drop `-ferry` onto the islands park).
    "boston-harbor-islands-ferry": "boston-harbor-island-ferry",
    # --- spelling / wording variants of legacy canonical slugs ---
    "museum-of-fine-arts-boston": "mfa",
    "museum-of-fine-arts": "mfa",
    "institute-of-contemporary-art": "ica-boston",
    "institute-of-contemporary-art-boston": "ica-boston",
    "john-f-kennedy-presidential-library-and-museum": "jfk-library",
    "john-f-kennedy-library-and-museum": "jfk-library",
    "dcr-massachusetts-state-parks": "ma-state-parks",
    "massachusetts-state-parks": "ma-state-parks",
    "massachusetts-parkspass": "ma-state-parks",
    "dcr-parkspass": "ma-state-parks",
    "massachusetts-state-parks-department-of-conservation-and-recreation": "ma-state-parks",
    "american-repertory-theatre": "american-repertory-theater",
    "american-repertory-theater-at-harvard-university": "american-repertory-theater",
    "american-rep-theater": "american-repertory-theater",
    "harvard-museums-of-science-culture": "harvard-museums-of-science-and-culture",
    "boston-children-s-museum": "boston-childrens-museum",
    "children-s-museum-easton": "childrens-museum-easton",
    "boch-center-tours": "boch-center",
    "charles-river-boat-tour": "charles-riverboat-tour",
    "how-do-you-see-the-world-experience-mapparium": "mapparium",
    "how-do-you-see-the-world-mapparium-globe": "mapparium",
    "larz-anderson-museum": "larz-anderson",
    "maplewood-country-day-camp-enrichment-center": "maplewood-day-camp",
    "royall-house-slave-quarters": "royall-house",
    "tacc-x-paddle-boston": "paddle-boston",
    "the-greenway-carousel": "greenway-carousel",
    "the-patriots-hall-of-fame": "patriots-hall-of-fame",
    "the-trustees": "trustees-of-reservations",
    "the-trustees-of-reservations-go-pass": "trustees-of-reservations",
    "trustees-go-pass": "trustees-of-reservations",
    "the-trustees-of-the-reservations": "trustees-of-reservations",
    "trustees-of-the-reservations": "trustees-of-reservations",
    "plimoth-patuxet-museums": "plimoth-patuxet",
    "plimoth-patuxent-museums": "plimoth-patuxet",
    "plimoth-patuxent": "plimoth-patuxet",
    "heritage-museums-and-gardens": "heritage-museums-gardens",
    "the-butterfly-place": "butterfly-place",
    "boston-harbor-island-ferry": "boston-harbor-island-ferry",
}


@lru_cache(maxsize=1)
def _legacy_map() -> dict[str, str]:
    """Build {legacy_slug -> canonical_slug} from the legacy attractions archive.

    Each record's own `slug` is canonical (maps to itself); each entry in its
    `legacy_slugs` maps to it. Missing archive → empty map (graceful).
    """
    m: dict[str, str] = {}
    if not _LEGACY_ATTRACTIONS.exists():
        return m
    data = json.loads(_LEGACY_ATTRACTIONS.read_text(encoding="utf-8"))
    records = data["attractions"] if isinstance(data, dict) else data
    for r in records:
        canon = r.get("slug")
        if not canon:
            continue
        m[canon] = canon
        for ls in r.get("legacy_slugs", []) or []:
            m.setdefault(ls, canon)
    return m


def _resolve_base(slug: str) -> str | None:
    """Hand map then legacy map. Returns the canonical, or None if unknown."""
    if slug in LEGACY_TO_CANONICAL:
        return LEGACY_TO_CANONICAL[slug]
    lm = _legacy_map()
    if slug in lm:
        return lm[slug]
    return None


def canonical(slug: str) -> str:
    """Return the canonical slug for `slug` (see module docstring for order)."""
    if not slug:
        return slug
    # 0/2: direct hand-map or legacy-map hit.
    direct = _resolve_base(slug)
    if direct is not None:
        return direct
    # 1: strip a pass-form suffix and retry, but only keep the result if the
    # stripped base actually resolves to a known canonical slug.
    base = _SUFFIX_RE.sub("", slug)
    if base != slug and base:
        resolved = _resolve_base(base)
        if resolved is not None:
            return resolved
    # 3: honest default — unknown slug stays itself (its own attraction).
    return slug
