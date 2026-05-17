"""Detect & promote museum-default-free age tiers from coupon cross-library consensus.

When a "Child/Youth, form=free, age_range.max=K" tier appears in >=3 library
coupons for the same attraction, that's almost certainly the museum's own policy
(not a coupon-granted benefit), so promote it to attraction.free_under_age and
remove it from the per-coupon audience_policies.
"""
from __future__ import annotations

from collections import Counter, defaultdict

from .slug_canonical import canonical

# Library-count threshold below which we won't promote — single-coupon outliers
# could just be a quirky one-off offer rather than the museum's default policy.
_MIN_LIBRARIES = 3


def _free_kid_max(policy: dict) -> int | None:
    """Return age_range.max for a Child/Youth free policy, else None."""
    if policy.get("audience") not in ("Child", "Youth"):
        return None
    if policy.get("form") != "free":
        return None
    ar = policy.get("age_range") or {}
    return ar.get("max")


def detect_free_under_age(coupons: dict[str, dict]) -> dict[str, int]:
    """Detect museum-default free-under-N age from cross-library coupon consensus.

    Args:
        coupons: dict keyed `<lib_id>_<slug>` → coupon record dict
            (status, capacity, audience_policies, ...).

    Returns:
        dict {canonical_slug: free_under_age_int} where consensus exists.
        Consensus = the same Child/Youth-free-max-K tier appears in >= 3
        libraries AND is the dominant (>= 50%) variant among all libraries
        that have ANY Child/Youth-free-max-* tier for that slug.

        free_under_age_int = K + 1 (a "max=2" coupon means kids <3 free).
    """
    # slug → {lib_id: max} (one vote per library — multiple coupons for same lib
    # collapse to the lowest max so we don't double-count).
    votes: dict[str, dict[str, int]] = defaultdict(dict)
    for key, rec in coupons.items():
        if not rec or rec.get("status") != "ok":
            continue
        lib_id = rec.get("library_id")
        raw_slug = rec.get("attraction_slug")
        if not lib_id or not raw_slug:
            # Fallback: parse key when fields are absent.
            if "_" not in key:
                continue
            lib_id, raw_slug = key.split("_", 1)
        slug = canonical(raw_slug)
        for p in rec.get("audience_policies") or []:
            m = _free_kid_max(p)
            if m is None:
                continue
            prev = votes[slug].get(lib_id)
            if prev is None or m < prev:
                votes[slug][lib_id] = m

    out: dict[str, int] = {}
    for slug, lib_max in votes.items():
        if len(lib_max) < _MIN_LIBRARIES:
            continue
        counter = Counter(lib_max.values())
        dominant_max, dominant_count = counter.most_common(1)[0]
        if dominant_count * 2 < len(lib_max):  # < 50%
            continue
        out[slug] = dominant_max + 1
    return out


def is_museum_default_policy(policy: dict, attraction_free_under_age: int | None) -> bool:
    """True iff `policy` is a Child/Youth-free row covered by the museum's own
    free-under-N policy on the attraction.

    Args:
        policy: an audience_policy dict.
        attraction_free_under_age: the museum's free-under threshold (the age at
            which kids must start paying), or None if unknown.

    Returns True only when the coupon's "free for <K and under" age window is
    already a strict subset of the museum's "free under N" — i.e. the coupon
    grants no benefit beyond what the museum gives everyone.
    """
    if attraction_free_under_age is None:
        return False
    if policy.get("audience") not in ("Child", "Youth"):
        return False
    if policy.get("form") != "free":
        return False
    ar = policy.get("age_range") or {}
    coupon_max = ar.get("max")
    if coupon_max is None:
        return False
    # Coupon says "free for ages <= coupon_max" → free under (coupon_max + 1).
    # Museum free-under-N covers everyone < N. The coupon adds nothing iff
    # (coupon_max + 1) <= N.
    return (coupon_max + 1) <= attraction_free_under_age
