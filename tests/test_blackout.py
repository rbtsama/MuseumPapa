from datetime import date
from malibbene.common.blackout import parse_blackout_phrase, is_blackout_on

def test_parse_specific_date_strips_year():
    out = parse_blackout_phrase("Closed December 25, 2026")
    assert out == [{"month": 12, "day": 25}]

def test_parse_july_4():
    out = parse_blackout_phrase("not valid July 4")
    assert out == [{"month": 7, "day": 4}]

def test_parse_recurring_sundays():
    out = parse_blackout_phrase("Sundays only", recurring_out=True)
    assert out == ([], ["sundays"])

def test_is_blackout_matches_month_day_regardless_of_year():
    rules = [{"month": 12, "day": 25}]
    assert is_blackout_on(rules, [], target=date(2027, 12, 25)) is True
    assert is_blackout_on(rules, [], target=date(2027, 12, 24)) is False

def test_is_blackout_recurring_weekday():
    assert is_blackout_on([], ["sundays"], target=date(2026, 5, 24)) is True
    assert is_blackout_on([], ["sundays"], target=date(2026, 5, 25)) is False
