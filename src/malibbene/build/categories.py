"""Attraction category normalization.

Maps the 21 raw labels Assabet platforms attach (Art / Crafts / Family /
Children / History / Architecture / Governance / Military / Tours / Nature /
Ocean / Sky / Zoo / Recreation / Music / Theatre / Dance / Entertainment /
Science / Technology / Sports) down to **7 canonical product categories**.

Rationale (decision made during audit, not by row count):
  - Tours dropped: all are also tagged History; "guided walk" is presentation,
    not subject.
  - Recreation dropped: mostly tagged Nature too; the rest fit Family/Children
    which they're already tagged with.
  - Sports kept distinct despite 2 rows — sports museums (Naismith /
    Patriots Hall of Fame) are a recognizable subject that sports-fan
    families will search by name.
  - Architecture / Governance / Military folded into History.
  - Ocean / Sky / Zoo folded into Nature.
  - Music / Theatre / Dance / Entertainment folded into Performance.
  - Technology folded into Science.
  - Crafts folded into Art.
  - Family folded into Children (this product is for family users; 'Family'
    label adds no filtering value when applied to ~72% of rows).
"""
from __future__ import annotations

CANONICAL = ["Children", "History", "Nature", "Science", "Art", "Performance", "Sports"]

RAW_TO_CANONICAL = {
    "Art": "Art", "Crafts": "Art",
    "Family": "Children", "Children": "Children",
    "History": "History", "Architecture": "History", "Governance": "History",
    "Military": "History", "Tours": "History",
    "Nature": "Nature", "Ocean": "Nature", "Sky": "Nature",
    "Zoo": "Nature", "Recreation": "Nature",
    "Performance": "Performance",
    "Music": "Performance", "Theatre": "Performance", "Dance": "Performance",
    "Entertainment": "Performance",
    "Science": "Science", "Technology": "Science",
    "Sports": "Sports",
}


def canonicalize(raw_categories: list[str]) -> list[str]:
    """Return deduplicated canonical categories in CANONICAL ordering.

    Unknown raw labels are silently dropped (caller can detect by comparing
    output length to input length if desired).
    """
    canon_set: set[str] = set()
    for c in raw_categories or []:
        mapped = RAW_TO_CANONICAL.get(c)
        if mapped:
            canon_set.add(mapped)
    return [c for c in CANONICAL if c in canon_set]
