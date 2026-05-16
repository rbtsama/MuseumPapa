"""Test the coupon summary string generator against the locked reference cases."""
from malibbene.build.coupon_summary import format_summary


def _cap(kind="people", n=4):
    return {"kind": kind, "n": n}


def _ap(audience, form, value=None, age_range=None, count=None):
    return {"audience": audience, "form": form, "value": value,
            "age_range": age_range, "count": count}


def test_simple_party_wide_half():
    assert format_summary(_cap(), [_ap("Everyone", "percent-off", 50)]) == "Up to 4 · 50% off"


def test_simple_party_wide_free():
    assert format_summary(_cap(), [_ap("Everyone", "free")]) == "Up to 4 · FREE"


def test_per_person_price():
    assert format_summary(_cap(), [_ap("Everyone", "per-person-price", 9)]) == "Up to 4 · $9/person"


def test_per_vehicle_free():
    assert format_summary(_cap("vehicle", None), [_ap("Vehicle", "free")]) == "Per vehicle · FREE"


def test_bonus_tier_kids_under_n_free():
    s = format_summary(_cap(), [
        _ap("Everyone", "percent-off", 50),
        _ap("Child", "free", age_range={"min": None, "max": 2}),
    ])
    assert s == "Up to 4 · 50% off · Kids under 3 free"


def test_adults_only():
    assert format_summary(_cap(), [_ap("Adult", "percent-off", 50)]) == "Up to 4 · Adults only · 50% off"


def test_mixed_adult_child_pricing():
    s = format_summary(_cap(), [
        _ap("Adult", "percent-off", 50, count=2),
        _ap("Child", "per-person-price", 1, count=2),
    ])
    assert s == "Up to 4 · 50% off (Adult) · $1/person (Child)"


def test_complex_three_audience_split():
    s = format_summary(_cap(), [
        _ap("Adult", "percent-off", 50),
        _ap("Child", "percent-off", 50, age_range={"min": 8, "max": 16}),
        _ap("Child", "dollar-off", 2, age_range={"min": None, "max": 7}),
    ])
    assert s == "Up to 4 · 50% off (Adult, Child 8-16) · $2 off (Child <8)"


def test_dollar_off_simple():
    assert format_summary(_cap(), [_ap("Everyone", "dollar-off", 5)]) == "Up to 4 · $5 off"


def test_unspecified_capacity():
    s = format_summary({"kind": "unspecified", "n": None},
                       [_ap("Everyone", "percent-off", 50)])
    assert s == "50% off"


def test_empty_policies_returns_empty_string():
    assert format_summary(_cap(), []) == ""
