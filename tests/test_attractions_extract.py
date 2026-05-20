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
