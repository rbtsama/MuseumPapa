from __future__ import annotations

from malibbene.build.coupons import summary_for


def test_jfk_library_shows_percent_off_not_free():
    """jfk-library: 'Single ticket 50% off' + a 'Child free' line.

    No adult/everyone-keyed audience exists, so summary_for must not let the
    free child line win — a paying visitor gets 50% off, not free admission.
    """
    aps = [
        {"audience": "Single ticket", "form": "percent-off", "value": 50},
        {"audience": "Child", "form": "free", "value": None},
    ]
    assert summary_for(aps) == "50% off"


def test_maplewood_shows_per_person_price_not_free():
    """maplewood-day-camp: $12/child plus a free-under-1 line -> $12/person."""
    aps = [
        {"audience": "Child", "form": "per-person-price", "value": 12},
        {"audience": "Child", "form": "free", "value": None},
    ]
    assert summary_for(aps) == "$12/person"


def test_all_free_stays_free():
    """A pass that is genuinely free for everyone must still read FREE."""
    aps = [
        {"audience": "Adult", "form": "free", "value": None},
        {"audience": "Child", "form": "free", "value": None},
    ]
    assert summary_for(aps) == "FREE"


def test_free_only_policy_stays_free():
    aps = [{"audience": "Everyone", "form": "free", "value": None}]
    assert summary_for(aps) == "FREE"


def test_integer_valued_float_drops_trailing_zero():
    """$9.0/person -> $9/person, but real decimals (e.g. $13.5) are kept (D3)."""
    assert summary_for([{"audience": "Everyone", "form": "per-person-price", "value": 9.0}]) == "$9/person"
    assert summary_for([{"audience": "Everyone", "form": "per-person-price", "value": 13.5}]) == "$13.5/person"
    assert summary_for([{"audience": "Adult", "form": "dollar-off", "value": 10.0}]) == "$10 off"
    assert summary_for([{"audience": "Adult", "form": "percent-off", "value": 50.0}]) == "50% off"


def test_adult_match_still_wins_over_a_stronger_form():
    """Explicit adult/everyone audience takes precedence over the strength rank."""
    aps = [
        {"audience": "Child", "form": "free", "value": None},
        {"audience": "Adult", "form": "dollar-off", "value": 5},
    ]
    assert summary_for(aps) == "$5 off"
