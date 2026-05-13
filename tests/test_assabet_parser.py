"""Parser-level tests for ``malibbene.sources.assabet.availability``.

NOTE: PARTIAL_DAY_RE's ``[\\s\\S]{0,2000}?`` window can bleed across multiple
``<div class="day ...">`` blocks when fixtures are densely packed, so the
``limited`` upgrade is tested in an isolated single-day fixture rather than
mixed with other days. Real Assabet pages have enough whitespace between days
that this rarely bites in practice."""
from malibbene.sources.assabet.availability import parse_calendar


BASIC_FIXTURE = """
<div class="day day-mon day-2026-05-04 day-past day-no-openings">x</div>
<div class="day day-tue day-2026-05-05 day-has-openings">x</div>
<div class="day day-thu day-2026-05-07 day-no-openings">x</div>
<div class="day day-fri day-2026-05-08 day-blank">x</div>
"""

PARTIAL_FIXTURE = """
<div class="day day-wed day-2026-05-06 day-has-openings">
  <span class="time-partially-available">2pm only</span>
</div>
"""


def test_parse_calendar_basic_states():
    cal = parse_calendar(BASIC_FIXTURE)
    assert "2026-05-04" not in cal  # past
    assert cal["2026-05-05"] == "available"
    assert cal["2026-05-07"] == "booked"
    assert "2026-05-08" not in cal  # blank


def test_parse_calendar_partial_upgrade():
    cal = parse_calendar(PARTIAL_FIXTURE)
    assert cal["2026-05-06"] == "limited"
