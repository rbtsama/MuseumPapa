"""Tests for museum_policy: detect & filter museum-default free age tiers."""
from __future__ import annotations

from malibbene.build.museum_policy import (
    detect_free_under_age,
    is_museum_default_policy,
)


def _coupon(lib_id: str, slug: str, *policies: dict) -> tuple[str, dict]:
    key = f"{lib_id}_{slug}"
    rec = {
        "library_id": lib_id,
        "attraction_slug": slug,
        "status": "ok",
        "capacity": {"kind": "people", "n": 4},
        "audience_policies": list(policies),
    }
    return key, rec


def _free_child(maxv: int) -> dict:
    return {"audience": "Child", "age_range": {"min": None, "max": maxv},
            "count": None, "form": "free", "value": None}


def test_detect_threshold_3_libraries():
    coupons = dict([
        _coupon("acton", "mos", _free_child(2)),
        _coupon("andover", "mos", _free_child(2)),
        _coupon("arlington", "mos", _free_child(2)),
    ])
    out = detect_free_under_age(coupons)
    assert out == {"mos": 3}


def test_detect_ignores_below_threshold():
    coupons = dict([
        _coupon("acton", "mos", _free_child(2)),
        _coupon("andover", "mos", _free_child(2)),
    ])
    assert detect_free_under_age(coupons) == {}


def test_detect_picks_dominant_variant():
    coupons = dict([
        _coupon("a", "zoo", _free_child(2)),
        _coupon("b", "zoo", _free_child(2)),
        _coupon("c", "zoo", _free_child(2)),
        _coupon("d", "zoo", _free_child(2)),
        _coupon("e", "zoo", _free_child(2)),
        _coupon("f", "zoo", _free_child(3)),
    ])
    out = detect_free_under_age(coupons)
    # 5 libraries say max=2 (dominant) → free_under_age = 2+1 = 3
    assert out == {"zoo": 3}


def test_detect_canonicalizes_slug():
    coupons = dict([
        _coupon("a", "museum-of-fine-arts", _free_child(2)),
        _coupon("b", "museum-of-fine-arts", _free_child(2)),
        _coupon("c", "mfa", _free_child(2)),
    ])
    out = detect_free_under_age(coupons)
    assert out == {"mfa": 3}


def test_detect_skips_non_ok_status():
    coupons = dict([
        _coupon("a", "mos", _free_child(2)),
        _coupon("b", "mos", _free_child(2)),
        _coupon("c", "mos", _free_child(2)),
    ])
    coupons["a_mos"]["status"] = "failed:parser"
    assert detect_free_under_age(coupons) == {}


def test_is_museum_default_policy_matches():
    policy = _free_child(2)
    assert is_museum_default_policy(policy, 3) is True


def test_is_museum_default_policy_below_threshold():
    # Coupon offers free up to age 5, museum default is only kids <3 → coupon
    # genuinely adds value, do NOT drop.
    policy = _free_child(5)
    assert is_museum_default_policy(policy, 3) is False


def test_is_museum_default_policy_equal_threshold():
    # Coupon max=2 (free <3), museum free_under=3 → exactly redundant.
    policy = _free_child(2)
    assert is_museum_default_policy(policy, 3) is True


def test_is_museum_default_policy_no_attraction_value():
    policy = _free_child(2)
    assert is_museum_default_policy(policy, None) is False


def test_is_museum_default_policy_wrong_audience():
    policy = {"audience": "Adult", "age_range": {"min": None, "max": 2},
              "form": "free", "value": None}
    assert is_museum_default_policy(policy, 3) is False


def test_is_museum_default_policy_wrong_form():
    policy = {"audience": "Child", "age_range": {"min": None, "max": 2},
              "form": "percent-off", "value": 50}
    assert is_museum_default_policy(policy, 3) is False


def test_is_museum_default_policy_no_max_age():
    policy = {"audience": "Child", "age_range": None,
              "form": "free", "value": None}
    assert is_museum_default_policy(policy, 3) is False
