"""Canonical slug mapping for attraction entities.

Some attractions are referenced by multiple slugs across platforms (Assabet vs
LibCal vs MuseumKey). This mapping collapses duplicates by mapping each legacy
slug to a single canonical winner. Applied in the build pipeline (attractions
accumulator + passes emitter) so downstream consumers only ever see canonical
slugs.
"""
from __future__ import annotations

# Legacy slug → canonical slug. Any slug not present here is canonical already.
LEGACY_TO_CANONICAL: dict[str, str] = {
    "museum-of-fine-arts": "mfa",
    "institute-of-contemporary-art-boston": "ica-boston",
    "john-f-kennedy-library-and-museum": "jfk-library",
    "the-trustees-of-the-reservations": "trustees-of-reservations",
    "trustees-of-the-reservations": "trustees-of-reservations",
    "plimoth-patuxet-museums": "plimoth-patuxet",
    "american-rep-theater": "american-repertory-theater",
    "massachusetts-state-parks-department-of-conservation-and-recreation": "ma-state-parks",
    "the-butterfly-place": "butterfly-place",
}


def canonical(slug: str) -> str:
    """Return the canonical slug for `slug`, or `slug` unchanged if not legacy."""
    return LEGACY_TO_CANONICAL.get(slug, slug)
