from malibbene.sources_v2.libcal.availability import (
    build_availability_url,
    parse_availability_html,
)


def test_build_availability_url_uses_institution_endpoint():
    url = build_availability_url(libcal_subdomain="bpl", pass_id="5bf37dc2bee6", date="2026-05-20")
    assert "bpl.libcal.com/pass/availability/institution" in url
    assert "museum=5bf37dc2bee6" in url
    assert "date=2026-05-20" in url


def test_parse_availability_html_extracts_days_with_status():
    # libcal returns an HTML fragment with one div.day per cell. status
    # comes from the inner s-lc-pass-<status> class.
    html = """
    <div class="day day-Mon day-2026-05-25">
      <div class="day-number">
        <span class="s-lc-pass-availability s-lc-pass-available">25</span>
      </div>
    </div>
    <div class="day day-Tue day-2026-05-26">
      <div class="day-number">
        <span class="s-lc-pass-availability s-lc-pass-unavailable">26</span>
      </div>
    </div>
    <div class="day day-Wed day-2026-05-27 day-other-month">
      <div class="day-number">
        <span class="s-lc-pass-availability s-lc-pass-available">27</span>
      </div>
    </div>
    """
    days = parse_availability_html(html)
    by_date = {d["date"]: d["status"] for d in days}
    assert by_date == {"2026-05-25": "available", "2026-05-26": "booked"}
    # day-other-month must be excluded:
    assert "2026-05-27" not in by_date


def test_parse_availability_handles_not_yet_available():
    html = """
    <div class="day day-Mon day-2026-08-15">
      <div class="day-number">
        <span class="s-lc-pass-availability s-lc-pass-not-yet-available">15</span>
      </div>
    </div>
    """
    days = parse_availability_html(html)
    assert days == [{"date": "2026-08-15", "status": "unavailable"}]
