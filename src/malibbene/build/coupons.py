"""Load + attach per-pass coupon data extracted by plan-9 subagents.

Reads data/raw/pass_coupons/<lib>_<slug>.json files written by Task 2.
"""
from __future__ import annotations

import json
from pathlib import Path

from malibbene.build.museum_policy import is_museum_default_policy


def coupon_coverage_gaps(passes: list, raw_root) -> list:
    """Silent-drop guard: return (library_id, attraction_slug) for every pass that
    shipped an EMPTY coupon although an authoritative pass_coupons file (status 'ok')
    exists for it. An empty list means coupon coverage is healthy. The build raises
    on a non-empty result so this class of bug can never ship unnoticed again."""
    pc = Path(raw_root) / "pass_coupons"
    gaps = []
    for p in passes:
        if p.get("coupon"):
            continue
        lib = p.get("library_id")
        for slug in (p.get("attraction_slug"), p.get("attraction_rawslug")):
            if not slug:
                continue
            f = pc / f"{lib}_{slug}.json"
            if f.exists():
                try:
                    if json.loads(f.read_text()).get("status") == "ok":
                        gaps.append((lib, p.get("attraction_slug")))
                        break
                except (ValueError, OSError):
                    pass
    return gaps


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


_STRENGTH = {"free": 6, "percent-off": 5, "dollar-off": 4, "per-person-price": 3, "discount": 2, "bogo": 1}
_ADULT = {"adult", "adults", "everyone", "all"}


def summary_for(audience_policies: list) -> str:
    """Mobile e-commerce style headline for the adult/Everyone policy (else the
    strongest by discount form). Matches the panel's couponSummary wording."""
    aps = audience_policies or []
    if not aps:
        return "discount unspecified"
    p = next((x for x in aps if str(x.get("audience", "")).lower() in _ADULT), None)
    if p is None:
        p = max(aps, key=lambda x: _STRENGTH.get(x.get("form"), 0))
    f, v = p.get("form"), p.get("value")
    if f == "free":
        return "FREE"
    if f == "percent-off":
        return f"{v}% off" if v is not None else "% off"
    if f == "dollar-off":
        return f"${v} off" if v is not None else "$ off"
    if f == "per-person-price":
        return f"${v}/person" if v is not None else "$/person"
    if f == "bogo":
        return "buy one get one free"
    return "discount"


def coupon_from_extract(rec: dict) -> dict:
    """Structured coupon (capacity / audience_policies / summary / source_phrase_block)
    from a data/raw/pass_coupons/ extraction record. Caller ensures status == 'ok'.

    This is the AUTHORITATIVE coupon source. Per-policy source_phrase is recovered
    from the record's `source_phrases` map (keyed by field path)."""
    sp = rec.get("source_phrases") or {}
    aps = []
    for i, p in enumerate(rec.get("audience_policies") or []):
        q = dict(p)
        ph = sp.get(f"audience_policies[{i}].form") or sp.get(f"audience_policies[{i}].value")
        if ph and "source_phrase" not in q:
            q["source_phrase"] = ph
        aps.append(q)
    cap = rec.get("capacity") or {}
    return {
        "capacity": {"kind": cap.get("kind", "unspecified"), "n": cap.get("n")},
        "audience_policies": aps,
        "summary": summary_for(aps),
        "source_phrase_block": rec.get("raw"),
    }


def restrictions_from_extract(rec: dict) -> dict | None:
    """Date restrictions in the structured passes.json shape from a pass_coupons rec.
    Returns None when there are no date-when restrictions (the common case)."""
    r = rec.get("restrictions") or {}
    # pass_coupons stores absolute "YYYY-MM-DD" strings; the structured schema uses
    # relative {month, day} (no year — years go stale, see redesign finding 5.2).
    blackout = []
    for d in r.get("blackout_dates") or []:
        if isinstance(d, dict) and d.get("month"):
            blackout.append({"month": d["month"], "day": d.get("day")})
        elif isinstance(d, str):
            parts = d.split("-")
            if len(parts) == 3:    # YYYY-MM-DD
                blackout.append({"month": int(parts[1]), "day": int(parts[2])})
            elif len(parts) == 2:  # MM-DD
                blackout.append({"month": int(parts[0]), "day": int(parts[1])})
    if not (blackout or r.get("weekdays_only") or r.get("seasonal")):
        return None
    return {
        "blackout": blackout,
        "blackout_recurring": [],
        "weekdays_only": bool(r.get("weekdays_only")),
        "seasonal": r.get("seasonal"),
        "advance_booking_required": False,
        "advance_booking_hours": None,
        "booking_frequency_limit": None,
        "late_return_penalty": None,
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
