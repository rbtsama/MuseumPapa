"""Calendar-parsing tests for ``malibbene.sources.libcal.availability``."""
from malibbene.sources.libcal.availability import parse_calendar


CAL_FIXTURE = """
<div class="day day-Mon day-2026-05-04 day-past">
  <span class="s-lc-pass-available">x</span></div></div>
<div class="day day-Tue day-2026-05-05 active">
  <span class="s-lc-pass-available">x</span></div></div>
<div class="day day-Wed day-2026-05-06 active">
  <span class="s-lc-pass-unavailable">x</span></div></div>
<div class="day day-Thu day-2026-05-07 active">
  <span class="s-lc-pass-not-yet-available">x</span></div></div>
<div class="day day-Fri day-2026-05-08 other-month">
  <span class="s-lc-pass-available">x</span></div></div>
"""


def test_parse_calendar_classifies_three_states():
    cal = parse_calendar(CAL_FIXTURE)
    assert cal["2026-05-05"] == "available"
    assert cal["2026-05-06"] == "booked"
    # Not-yet-available collapses to booked (BPL monthly-release window).
    assert cal["2026-05-07"] == "booked"


def test_parse_calendar_skips_past_and_other_month():
    cal = parse_calendar(CAL_FIXTURE)
    assert "2026-05-04" not in cal  # day-past
    assert "2026-05-08" not in cal  # other-month
