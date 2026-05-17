"""Load + attach per-pass coupon data extracted by plan-9 subagents.

Reads data/raw/pass_coupons/<lib>_<slug>.json files written by Task 2.
"""
from __future__ import annotations

from malibbene.build.museum_policy import is_museum_default_policy


def coupon_block(rec: dict | None, *, museum_free_under_age: int | None = None) -> dict:
    """Return a Coupon dict for a pass. If rec is missing/failed, return a
    well-formed empty coupon (kind=unspecified, no policies).

    When `museum_free_under_age` is provided, drop any audience_policies that
    merely restate the museum's own free-under-N policy — UNLESS doing so would
    leave the coupon empty (in which case we keep at least one policy so the
    pass doesn't look like it offers literally nothing).
    """
    if not rec or rec.get("status") != "ok":
        return {
            "capacity": {"kind": "unspecified", "n": None},
            "audience_policies": [],
        }
    cap = rec.get("capacity") or {}
    cap_block = {
        "kind": cap.get("kind", "unspecified"),
        "n": cap.get("n"),
    }
    aps = list(rec.get("audience_policies") or [])
    if museum_free_under_age is not None and aps:
        kept = [p for p in aps if not is_museum_default_policy(p, museum_free_under_age)]
        if kept:  # only filter if something non-redundant remains
            aps = kept
    return {
        "capacity": cap_block,
        "audience_policies": aps,
    }


def restrictions_block(rec: dict | None) -> dict | None:
    if not rec or rec.get("status") != "ok":
        return None
    r = rec.get("restrictions") or {}
    if not any([r.get("blackout_dates"), r.get("weekdays_only"),
                r.get("seasonal"), r.get("reservation_required")]):
        return None
    return {
        "blackout_dates": bool(r.get("blackout_dates")),
        "weekdays_only": bool(r.get("weekdays_only")),
        "seasonal": r.get("seasonal"),
        "reservation_required": bool(r.get("reservation_required")),
    }
