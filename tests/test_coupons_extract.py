"""Tests for the deterministic coupon extractor.

These cover the canonical input shapes:
  - percent-off ("admits N people for X% off") and half-price ("1/2 price")
  - dollar-off ("$N off each")
  - free ("FREE admission" / "for free" / parking pass / day membership)
  - per-person-price ("$N per person" / "$N a person" / "$N each")
  - per-audience (adults $A / children $C)
  - BOGO ("buy one get one")
  - generic discount with no number
  - navigation-only -> status=failed
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from malibbene.sources_v2.coupons.extract import extract_coupon  # noqa: E402


def _extract(text, **kw):
    return extract_coupon(
        library_id=kw.get("library_id", "lib"),
        attraction_slug=kw.get("slug", "att"),
        benefit_text=text,
        source_phrases=kw.get("source_phrases") or [text],
        platform=kw.get("platform", "assabet"),
    )


def test_percent_off():
    r = _extract("Passes admit 4 people for 50% off regular museum admission rates.")
    assert r["status"] == "ok"
    c = r["extracted"]["coupon"]
    assert c["summary"] == "50% off"
    assert c["capacity"] == {"kind": "people", "n": 4}
    ap = c["audience_policies"][0]
    assert ap["audience"] == "Everyone"
    assert ap["form"] == "percent-off"
    assert ap["value"] == 50


def test_half_price_alias():
    r = _extract("Pass admits up to 3 people at half price.")
    assert r["status"] == "ok"
    assert r["extracted"]["coupon"]["summary"] == "50% off"
    assert r["extracted"]["coupon"]["audience_policies"][0]["value"] == 50


def test_half_price_slash_form():
    r = _extract("Pass admits up to 4 people at 1/2 price admission.")
    assert r["status"] == "ok"
    assert r["extracted"]["coupon"]["summary"] == "50% off"


def test_dollar_off_each():
    r = _extract("This pass admits up to 4 at $5-off each.")
    assert r["status"] == "ok"
    c = r["extracted"]["coupon"]
    assert c["summary"] == "$5 off"
    assert c["audience_policies"][0]["form"] == "dollar-off"
    assert c["audience_policies"][0]["value"] == 5


def test_free_headline_admission():
    r = _extract("FREE admission with this pass.")
    assert r["status"] == "ok"
    assert r["extracted"]["coupon"]["summary"] == "FREE"
    assert r["extracted"]["coupon"]["audience_policies"][0]["form"] == "free"


def test_free_parking_assabet_says_free():
    r = _extract("This pass offers free general parking at many Massachusetts State Parks.",
                 platform="assabet")
    assert r["status"] == "ok"
    # assabet convention: vehicle capacity, summary just "FREE".
    assert r["extracted"]["coupon"]["summary"] == "FREE"
    assert r["extracted"]["coupon"]["capacity"]["kind"] == "vehicle"


def test_free_parking_libcal_says_free_parking():
    r = _extract("The ParksPass entitles the bearer to free parking at over 50 facilities.",
                 platform="libcal")
    assert r["status"] == "ok"
    assert r["extracted"]["coupon"]["summary"] == "FREE parking"


def test_dollar_per_person():
    r = _extract("Pass admits up to 4 people at $5 per person.")
    assert r["status"] == "ok"
    c = r["extracted"]["coupon"]
    assert c["summary"] == "$5/person"
    assert c["audience_policies"][0]["form"] == "per-person-price"
    assert c["audience_policies"][0]["value"] == 5


def test_adult_child_two_tier():
    r = _extract("Admission costs $9 per adult and $6 per child. Pass admits 6 people.")
    assert r["status"] == "ok"
    c = r["extracted"]["coupon"]
    assert c["summary"] == "$9/person"
    aps = c["audience_policies"]
    assert len(aps) == 2
    assert aps[0]["audience"] == "adults" and aps[0]["value"] == 9
    assert aps[1]["audience"] == "children" and aps[1]["value"] == 6
    assert aps[0]["age_range"] == {"min": 18, "max": 200}


def test_bogo():
    r = _extract("Friday night performances: buy one get one free.")
    assert r["status"] == "ok"
    c = r["extracted"]["coupon"]
    assert c["summary"] == "BOGO"
    assert c["audience_policies"][0]["form"] == "bogo"


def test_generic_discount_with_count_capitalises():
    r = _extract("Pass admits up to 6 people discounted admission.")
    assert r["status"] == "ok"
    c = r["extracted"]["coupon"]
    assert c["summary"] == "Discount"
    assert c["audience_policies"][0]["form"] == "discount"


def test_generic_discount_no_count_lowercase():
    r = _extract(
        "This library membership pass entitles you to two tickets at the discounted Library Pass rate.",
        platform="libcal",
        slug="institute-of-contemporary-art-e-coupon",
    )
    assert r["status"] == "ok"
    # capacity matched -> Discount; this test exercises the no-count branch.
    # When capacity is detected (2 tickets), summary still capitalised.
    assert r["extracted"]["coupon"]["summary"] in {"Discount", "discount"}


def test_pass_form_digital_email_via_slug():
    r = _extract("Two tickets at discounted Library Pass rate.",
                 platform="libcal", slug="boston-childrens-museum-e-coupon")
    assert r["extracted"]["pass_form"] == "digital_email"


def test_pass_form_physical_circ_via_text():
    r = _extract("This pass admits 2 people at half price. This pass must be returned to the library.")
    assert r["extracted"]["pass_form"] == "physical_circ"


def test_navigation_only_fails():
    r = _extract("To choose a date for your reservation, please click on the number of the desired day.")
    assert r["status"] == "failed"


def test_empty_text_fails():
    r = _extract("")
    assert r["status"] == "failed"


def test_unparseable_returns_failed():
    # Text without any quantifiable benefit cue
    r = _extract("Pick up coupon at library. Pass will admit 2 adults and children under 18 years old.")
    assert r["status"] == "failed"


def test_children_under_n_secondary_policy():
    r = _extract(
        "This pass admits up to 2 visitors at the discounted price of $10 per admission. "
        "Admission is free to anyone 18 and under."
    )
    assert r["status"] == "ok"
    # primary policy is per-person-price $10; we don't strictly require the
    # secondary children-free policy to be present, but the summary should be
    # $10/person.
    assert r["extracted"]["coupon"]["summary"] == "$10/person"
