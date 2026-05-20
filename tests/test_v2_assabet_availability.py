from pathlib import Path
from malibbene.sources_v2.assabet.availability import parse_calendar_html

FIXT = Path(__file__).parent / "fixtures/assabet/wakefield_calendar.html"


def test_parse_calendar_returns_dates_with_status():
    days = parse_calendar_html(FIXT.read_text(encoding="utf-8"))
    assert len(days) >= 14
    sample = days[0]
    assert "date" in sample and "status" in sample
    assert sample["status"] in {"available", "booked", "unavailable", "closed"}
