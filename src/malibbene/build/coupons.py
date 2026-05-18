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
    # Per-vehicle capacity is "one carload" unless the source says otherwise.
    # Extraction leaves n=None on all 59 vehicle rows; default it so the UI
    # can render "Per vehicle (1 car)" instead of an ambiguous bare label.
    if cap_block["kind"] == "vehicle" and cap_block["n"] is None:
        cap_block["n"] = 1
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
    """Return pass-level date restrictions, or None when the pass has none.

    Only date-when restrictions live here (blackout / weekdays-only / seasonal).
    These are negotiated between the library and the attraction and apply
    specifically to pass-holders. "Does the museum require a timed-entry
    reservation" is NOT here — that's a museum-side policy applying to all
    visitors regardless of pass, and lives on attraction.museum_reservation.
    """
    if not rec or rec.get("status") != "ok":
        return None
    r = rec.get("restrictions") or {}
    blackout_dates = r.get("blackout_dates") or []
    if not isinstance(blackout_dates, list):
        # Legacy bool fallback (should not occur after schema upgrade)
        blackout_dates = [] if not blackout_dates else []
    if not any([blackout_dates, r.get("weekdays_only"), r.get("seasonal")]):
        return None
    return {
        "blackout_dates": blackout_dates,
        "weekdays_only": bool(r.get("weekdays_only")),
        "seasonal": r.get("seasonal"),
    }
