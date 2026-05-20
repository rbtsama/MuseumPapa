from malibbene.sources_v2.libcal.availability import (
    build_availability_url,
    parse_availability_json,
)


def test_build_availability_url_uses_institution_endpoint():
    url = build_availability_url(libcal_subdomain="bpl", pass_id="12345", date="2026-05-20")
    assert "bpl.libcal.com/pass/availability/institution" in url
    assert "museum=12345" in url
    assert "date=2026-05-20" in url


def test_parse_availability_returns_per_branch_or_aggregate():
    sample = {
        "available": [{"date": "2026-05-20"}, {"date": "2026-05-21"}],
        "booked": [{"date": "2026-05-22"}],
    }
    days = parse_availability_json(sample)
    assert {"date": "2026-05-20", "status": "available"} in days
    assert {"date": "2026-05-22", "status": "booked"} in days
