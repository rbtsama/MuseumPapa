"""Load + attach per-pass coupon data extracted by plan-9 subagents.

Reads data/raw/pass_coupons/<lib>_<slug>.json files written by Task 2.
"""
from __future__ import annotations

from malibbene.build.coupon_summary import format_summary


def coupon_block(rec: dict | None) -> dict:
    """Return a Coupon dict for a pass. If rec is missing/failed, return a
    well-formed empty coupon (kind=unspecified, no policies)."""
    if not rec or rec.get("status") != "ok":
        return {
            "capacity": {"kind": "unspecified", "n": None},
            "audience_policies": [],
            "summary": "",
        }
    cap = rec.get("capacity") or {}
    cap_block = {
        "kind": cap.get("kind", "unspecified"),
        "n": cap.get("n"),
    }
    aps = list(rec.get("audience_policies") or [])
    return {
        "capacity": cap_block,
        "audience_policies": aps,
        "summary": format_summary(cap_block, aps),
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
