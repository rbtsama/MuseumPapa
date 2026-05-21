"""Tests for the four deterministic attraction extractors.

Covered:
- visitor_eligibility: MA-resident hit, false-positive rejection, locals-free,
  no-html stub.
- reservation: timed_entry detection, walk-in default, booking_url match
  on known host + path patterns, pass_holder_url detection.
- prices: $-token + audience-keyword pairing, negative-context rejection
  (membership/parking fee/per-day).
- hours: day-range parsing (Mon-Fri 10-5) + 12h->24h conversion, "Closed Mondays".
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pytest  # noqa: E402

from malibbene.sources_v2.attractions.extract_visitor_eligibility import (  # noqa: E402
    extract_visitor_eligibility, html_to_text,
)
from malibbene.sources_v2.attractions.extract_reservation import (  # noqa: E402
    extract_reservation,
)
from malibbene.sources_v2.attractions.extract_prices import extract_prices  # noqa: E402
from malibbene.sources_v2.attractions.extract_hours import extract_hours  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures: build a tiny raw_root with synthetic HTML files
# ---------------------------------------------------------------------------

@pytest.fixture
def raw_root(tmp_path: Path) -> Path:
    base = tmp_path / "raw"
    (base / "attractions" / "pages").mkdir(parents=True)
    (base / "attractions" / "subpages").mkdir(parents=True)
    return base


def _write_page(raw_root: Path, slug: str, html: str) -> None:
    (raw_root / "attractions" / "pages" / f"{slug}.html").write_text(
        html, encoding="utf-8",
    )


def _write_sub(raw_root: Path, slug: str, name: str, html: str) -> None:
    (raw_root / "attractions" / "subpages" / f"{slug}__{name}.html").write_text(
        html, encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# visitor_eligibility
# ---------------------------------------------------------------------------

def test_visitor_eligibility_ma_resident(raw_root: Path):
    html = "<html><body>Massachusetts residents enjoy free admission on Sundays.</body></html>"
    _write_page(raw_root, "slug-a", html)
    r = extract_visitor_eligibility("slug-a", raw_root)
    assert r["status"] == "ok"
    e = r["extracted"]
    assert e["residency"] == "ma_resident"
    assert e["scope"] == "MA"
    assert e["locals_free"] is True


def test_visitor_eligibility_false_positive_president(raw_root: Path):
    html = "<html><body>President and Fellows of Harvard College. (c) 2025</body></html>"
    _write_page(raw_root, "slug-b", html)
    r = extract_visitor_eligibility("slug-b", raw_root)
    assert r["extracted"]["residency"] == "unknown"


def test_visitor_eligibility_animal_resident(raw_root: Path):
    html = "<html><body>Visit our resident otter and resident sheep!</body></html>"
    _write_page(raw_root, "slug-c", html)
    r = extract_visitor_eligibility("slug-c", raw_root)
    assert r["extracted"]["residency"] == "unknown"


def test_visitor_eligibility_locals_free_day(raw_root: Path):
    html = (
        "<html><body>Saugus residents can enjoy free admission to the museum "
        "on Saturday, May 30.</body></html>"
    )
    _write_page(raw_root, "slug-d", html)
    r = extract_visitor_eligibility("slug-d", raw_root)
    e = r["extracted"]
    assert e["locals_free"] is True
    assert e["residency"] == "none"


def test_visitor_eligibility_no_html(raw_root: Path):
    r = extract_visitor_eligibility("nonexistent", raw_root)
    assert r["status"] == "ok"
    assert r["extracted"]["residency"] == "unknown"


# ---------------------------------------------------------------------------
# reservation
# ---------------------------------------------------------------------------

def test_reservation_timed_entry(raw_root: Path):
    html = (
        '<html><body>Timed entry required. <a href="https://tickets.example/buy">'
        "Buy tickets</a></body></html>"
    )
    _write_page(raw_root, "att1", html)
    r = extract_reservation("att1", raw_root)
    e = r["extracted"]
    assert e["required"] == "timed_entry"
    assert e["booking_url"] is not None


def test_reservation_walk_in_default(raw_root: Path):
    html = (
        '<html><body>Welcome! We hope you enjoy your visit. '
        '<a href="https://example.org/tickets">Tickets</a></body></html>'
    )
    _write_page(raw_root, "att2", html)
    r = extract_reservation("att2", raw_root)
    e = r["extracted"]
    assert e["required"] == "walk_in_ok"
    assert "/tickets" in (e["booking_url"] or "")


def test_reservation_known_booking_host(raw_root: Path):
    html = (
        '<html><body>Tickets sold via partner. '
        '<a href="https://www.eventbrite.com/o/foo">Eventbrite</a></body></html>'
    )
    _write_page(raw_root, "att3", html)
    r = extract_reservation("att3", raw_root)
    assert "eventbrite" in (r["extracted"]["booking_url"] or "")


def test_reservation_pass_holder_url(raw_root: Path):
    html = (
        '<html><body><a href="https://example.org/library-pass-program">'
        "Library Pass Program</a></body></html>"
    )
    _write_page(raw_root, "att4", html)
    r = extract_reservation("att4", raw_root)
    e = r["extracted"]
    assert e["pass_holder_path"] == "dedicated_pass_holders_url"
    assert "library-pass-program" in (e["pass_holder_url"] or "")


# ---------------------------------------------------------------------------
# prices
# ---------------------------------------------------------------------------

def test_prices_adult_child(raw_root: Path):
    html = "<html><body>Admission: Adults $24, Children (1-15) $20.</body></html>"
    _write_page(raw_root, "p1", html)
    r = extract_prices("p1", raw_root)
    prices = r["extracted"]["prices"]
    audiences = {p["audience"]: p["price"] for p in prices}
    assert audiences.get("adult") == 24.0
    assert audiences.get("child") == 20.0


def test_prices_rejects_membership_context(raw_root: Path):
    html = "<html><body>Annual Membership: $150 (adults).</body></html>"
    _write_page(raw_root, "p2", html)
    r = extract_prices("p2", raw_root)
    # negative context "Annual Membership" should reject the $150 hit.
    assert r["extracted"]["prices"] == []


def test_prices_rejects_parking_fee(raw_root: Path):
    html = "<html><body>Parking fee: $5 per vehicle. Adults pay $20.</body></html>"
    _write_page(raw_root, "p3", html)
    r = extract_prices("p3", raw_root)
    prices = r["extracted"]["prices"]
    # $5 (parking) rejected, $20 (adult) kept
    assert any(p["audience"] == "adult" and p["price"] == 20.0 for p in prices)
    assert not any(p["price"] == 5.0 for p in prices)


def test_prices_label_after_price_with_dash(raw_root: Path):
    # Real wenham-museum markup: "PRICE - LABEL" list (label follows its price).
    html = (
        "<html><body>Individual Admission Rates $15.00 &#8211; Adults "
        "$10.00 &#8211; Seniors (ages 65+) $10.00 &#8211; Children ages 2 &#8211; 18"
        "</body></html>"
    )
    _write_page(raw_root, "p4", html)
    r = extract_prices("p4", raw_root)
    aud = {(p["audience"], p["price"]) for p in r["extracted"]["prices"]}
    assert ("adult", 15.0) in aud
    assert ("senior", 10.0) in aud
    assert ("child", 10.0) in aud


def test_prices_uss_suggested_donation_tiers(raw_root: Path):
    # USS Constitution Museum: pay-what-you-wish suggested tiers. Keep the
    # baseline "Standard" tier as the general (adult) admission; drop the
    # "Pay it Forward" and "Reduced" optional tiers and the donation widget.
    html = (
        "<html><body>Give Amount $2,500.00 $1,000.00 $25.00 "
        "The Museum has suggested admission tiers of: "
        "Pay it Forward: $25 per person Standard: $15 per person "
        "Reduced: Free &#8211; $10 per person</body></html>"
    )
    _write_sub(raw_root, "p5", "hours", html)
    r = extract_prices("p5", raw_root)
    rows = r["extracted"]["prices"]
    assert rows == [{"audience": "adult", "price": 15.0, "age_range": None,
                     "source_phrase": rows[0]["source_phrase"]}]
    # The $25 / $10 suggested tiers and donation buttons must NOT appear.
    assert not any(p["price"] in (25.0, 10.0, 2500.0, 1000.0)
                   for p in rows)


# ---------------------------------------------------------------------------
# hours
# ---------------------------------------------------------------------------

def test_hours_day_range_12h(raw_root: Path):
    html = "<html><body>Open Mon-Fri 10am-5pm.</body></html>"
    _write_page(raw_root, "h1", html)
    r = extract_hours("h1", raw_root)
    h = r["extracted"]["hours"]
    assert h["monday"] == "10:00-17:00"
    assert h["friday"] == "10:00-17:00"
    assert h["sunday"] == "unknown"


def test_hours_closed_mondays(raw_root: Path):
    html = "<html><body>Tuesday-Sunday 9:00-17:00. Closed Mondays.</body></html>"
    _write_page(raw_root, "h2", html)
    r = extract_hours("h2", raw_root)
    h = r["extracted"]["hours"]
    assert h["monday"] == "closed"
    assert h["tuesday"] == "09:00-17:00"


def test_hours_no_html_returns_all_unknown(raw_root: Path):
    r = extract_hours("none-found", raw_root)
    h = r["extracted"]["hours"]
    assert all(v == "unknown" for v in h.values())


def test_hours_open_daily(raw_root: Path):
    # heritage-museums-gardens / the-house-of-seven-gables style.
    html = "<html><body>Open Daily 10 am-5 pm, until October 18.</body></html>"
    _write_page(raw_root, "hd", html)
    h = extract_hours("hd", raw_root)["extracted"]["hours"]
    assert all(v == "10:00-17:00" for v in h.values())


def test_hours_open_daily_from_to(raw_root: Path):
    # harvard-museum-of-natural-history style.
    html = "<html><body>Hours Open daily from 9:00 am to 5:00 pm.</body></html>"
    _write_page(raw_root, "hd2", html)
    h = extract_hours("hd2", raw_root)["extracted"]["hours"]
    assert all(v == "09:00-17:00" for v in h.values())


def test_hours_am_pm_with_periods_and_endash(raw_root: Path):
    # new-england-botanic-garden style: "10 a.m.-5 p.m." with periods.
    html = "<html><body>GENERAL ADMISSION HOURS Open daily: 10 a.m.&#8211;5 p.m.</body></html>"
    _write_page(raw_root, "hp", html)
    h = extract_hours("hp", raw_root)["extracted"]["hours"]
    assert all(v == "10:00-17:00" for v in h.values())


def test_hours_endash_day_range(raw_root: Path):
    # old-sturbridge-village: "Wednesday - Sunday 9:30 a.m. - 5:00 p.m." (en-dash entity).
    html = (
        "<html><body>Currently open Wednesday &#8211; Sunday "
        "9:30 a.m. &#8211; 5:00 p.m.</body></html>"
    )
    _write_page(raw_root, "hr", html)
    h = extract_hours("hr", raw_root)["extracted"]["hours"]
    assert h["wednesday"] == "09:30-17:00"
    assert h["sunday"] == "09:30-17:00"
    assert h["monday"] == "unknown"


def test_hours_time_before_day_range(raw_root: Path):
    # larz-anderson: "open 10AM - 3PM | Tuesday - Sunday".
    html = "<html><body>The Museum is open 10AM - 3PM | Tuesday - Sunday.</body></html>"
    _write_page(raw_root, "tb", html)
    h = extract_hours("tb", raw_root)["extracted"]["hours"]
    assert h["tuesday"] == "10:00-15:00"
    assert h["sunday"] == "10:00-15:00"
    assert h["monday"] == "unknown"


def test_hours_and_pair(raw_root: Path):
    # boston-athenaeum: "Friday and Saturday: 9 am - 5 pm".
    html = "<html><body>Hours Friday and Saturday: 9 am &#8211; 5 pm. Sunday: Closed</body></html>"
    _write_page(raw_root, "ap", html)
    h = extract_hours("ap", raw_root)["extracted"]["hours"]
    assert h["friday"] == "09:00-17:00"
    assert h["saturday"] == "09:00-17:00"
    assert h["sunday"] == "closed"


def test_hours_weekend_split(raw_root: Path):
    # new-england-aquarium: "Mon.-Fri.: 9-5; Weekends: 9-6".
    html = (
        "<html><body>HOURS OF OPERATION Mon.&#8211;Fri.: 9:00 a.m.&#8211;5:00 p.m. "
        "Weekends: 9:00 a.m.&#8211;6:00 p.m.</body></html>"
    )
    _write_page(raw_root, "wk", html)
    h = extract_hours("wk", raw_root)["extracted"]["hours"]
    assert h["monday"] == "09:00-17:00"
    assert h["friday"] == "09:00-17:00"
    assert h["saturday"] == "09:00-18:00"
    assert h["sunday"] == "09:00-18:00"


def test_hours_per_day_colon_with_closed(raw_root: Path):
    # ecotarium: "Monday : Closed  Tuesday : 10:00 am - 5:00 pm ...".
    html = (
        "<html><body>Monday : Closed Tuesday : 10:00 am &#8211; 5:00 pm "
        "Wednesday : 10:00 am &#8211; 5:00 pm</body></html>"
    )
    _write_page(raw_root, "pd", html)
    h = extract_hours("pd", raw_root)["extracted"]["hours"]
    assert h["monday"] == "closed"
    assert h["tuesday"] == "10:00-17:00"
    assert h["wednesday"] == "10:00-17:00"


def test_hours_closed_day_range(raw_root: Path):
    # wenham-museum: "Sunday - Tuesday: CLOSED".
    html = (
        "<html><body>Wednesday &#8211; Saturday: 9 am &#8211; 4 pm "
        "Sunday - Tuesday: CLOSED</body></html>"
    )
    _write_page(raw_root, "cr", html)
    h = extract_hours("cr", raw_root)["extracted"]["hours"]
    assert h["wednesday"] == "09:00-16:00"
    assert h["saturday"] == "09:00-16:00"
    assert h["sunday"] == "closed"
    assert h["monday"] == "closed"
    assert h["tuesday"] == "closed"


def test_hours_pm_inferred_for_small_end(raw_root: Path):
    # davis-farmland: "Monday - Friday Open 9:30-4 PM" -> end is 16:00 not 04:00.
    html = "<html><body>Open Monday - Friday 9:30-4 PM, last admission 3 PM.</body></html>"
    _write_page(raw_root, "pm", html)
    h = extract_hours("pm", raw_root)["extracted"]["hours"]
    assert h["monday"] == "09:30-16:00"
    assert h["friday"] == "09:30-16:00"


def test_hours_pm_inferred_for_small_start(raw_root: Path):
    # orchard-house / aviation: "Sundays 1 - 5 pm" -> 13:00-17:00 not 01:00.
    html = "<html><body>Sunday 1 &#8211; 5 pm</body></html>"
    _write_page(raw_root, "ps", html)
    h = extract_hours("ps", raw_root)["extracted"]["hours"]
    assert h["sunday"] == "13:00-17:00"


def test_hours_ignores_age_range(raw_root: Path):
    # orchard-house: "Camp for ages 8 - 12 Monday - Friday" must NOT be hours.
    html = "<html><body>Little Women Camp for ages 8 - 12 Monday - Friday.</body></html>"
    _write_page(raw_root, "ag", html)
    h = extract_hours("ag", raw_root)["extracted"]["hours"]
    assert h["monday"] == "unknown"
    assert h["friday"] == "unknown"


def test_hours_daily_schedule_header_not_open_daily(raw_root: Path):
    # american-heritage: "DAILY SCHEDULE MONDAY 10-5 TUESDAY CLOSED" - the
    # "DAILY SCHEDULE" header must not collapse all 7 days to open.
    html = (
        "<html><body>DAILY SCHEDULE MONDAY 10:00 AM to 5:00 PM "
        "TUESDAY CLOSED WEDNESDAY 10:00 AM to 5:00 PM</body></html>"
    )
    _write_page(raw_root, "ds", html)
    h = extract_hours("ds", raw_root)["extracted"]["hours"]
    assert h["tuesday"] == "closed"
    assert h["monday"] == "10:00-17:00"
    assert h["wednesday"] == "10:00-17:00"


# ---------------------------------------------------------------------------
# subpage merging
# ---------------------------------------------------------------------------

def test_extractors_read_subpages(raw_root: Path):
    _write_page(raw_root, "att5", "<html><body>About us page.</body></html>")
    _write_sub(raw_root, "att5", "visit",
               '<html><body>Open Wed-Sun 10am-4pm. '
               '<a href="https://example.org/tickets">Tickets</a></body></html>')
    r_hours = extract_hours("att5", raw_root)
    assert r_hours["extracted"]["hours"]["wednesday"] == "10:00-16:00"
    r_res = extract_reservation("att5", raw_root)
    assert r_res["extracted"]["booking_url"] is not None


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def test_html_to_text_collapses_whitespace():
    raw = "<html>  <p>Hello\n\nworld</p><script>bad();</script></html>"
    t = html_to_text(raw)
    assert "Hello" in t
    assert "world" in t
    assert "bad();" not in t
