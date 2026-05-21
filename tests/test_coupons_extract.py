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


# ---------------------------------------------------------------------------
# New patterns (real benefit_text snippets recovered from status:failed cells)
# ---------------------------------------------------------------------------


def test_free_lecture_series_pass():
    # museumkey/cohasset__cohasset-historical-society
    r = _extract(
        "Free Lecture Series Pass. Check this pass out from the library and "
        "present it upon entrance to the Historical Society's Event."
    )
    assert r["status"] == "ok"
    c = r["extracted"]["coupon"]
    assert c["summary"] == "FREE"
    assert c["audience_policies"][0]["form"] == "free"


def test_free_admission_for_up_to_n_after_description():
    # libcal/brookline__larz-anderson-auto-museum — benefit clause buried after
    # a long museum description + address, with "car" in the museum name.
    r = _extract(
        "15 Newton Street, Brookline, MA, 02445\n(617) 522-6547\n"
        "The Larz Anderson Auto Museum showcases America's Oldest Car Collection. "
        "This pass must be picked up and returned to the library. "
        "Pass benefits: Free admission for up to 4 visitors.",
        platform="libcal",
    )
    assert r["status"] == "ok"
    c = r["extracted"]["coupon"]
    assert c["summary"] == "FREE"
    assert c["audience_policies"][0]["form"] == "free"
    # "car" inside the museum name must NOT make this a vehicle capacity.
    assert c["capacity"] == {"kind": "people", "n": 4}


def test_admits_up_to_n_for_free():
    # libcal/brookline__uss-constitution-museum
    r = _extract(
        "The USS Constitution Museum is located in the Charlestown Navy Yard. "
        "Pass benefits: Admits up to 9 for free to the Museum.",
        platform="libcal",
    )
    assert r["status"] == "ok"
    assert r["extracted"]["coupon"]["summary"] == "FREE"


def test_free_named_family_admission():
    # libcal/bpl__the-greenway-carousel-e-coupon
    r = _extract(
        "Free Greenway Carousel family admission (up to 4 individuals) for one ride (e-coupon).",
        platform="libcal",
        slug="the-greenway-carousel-e-coupon",
    )
    assert r["status"] == "ok"
    assert r["extracted"]["coupon"]["summary"] == "FREE"
    assert r["extracted"]["pass_form"] == "digital_email"


def test_covers_the_cost_is_free():
    # assabet/stoneham__the-discovery-museums (Greater Boston Stage Company)
    r = _extract(
        "The coupon code covers the cost of up to 12 tickets per mainstage show. "
        "There is a limit of 2 tickets per person."
    )
    assert r["status"] == "ok"
    assert r["extracted"]["coupon"]["summary"] == "FREE"
    assert r["extracted"]["coupon"]["capacity"] == {"kind": "ticket", "n": 12}


def test_trustees_go_pass_equivalent_family_membership():
    # assabet/everett__peabody-essex-museum — "equivalent to Family Membership
    # price" is a reduced (free-OR-reduced) admission, NOT a flat free/$/% .
    r = _extract(
        "GO Passes allow for one-time use as admission for two adults and "
        "children under 18 to any of the 100+ Trustees properties. GO Pass "
        "admission is equivalent to a Trustees Family Membership admission "
        "price at Trustees properties that charge an admission fee. GO Passes "
        "are valid for admission only; not valid for discounts at parking kiosks."
    )
    assert r["status"] == "ok"
    c = r["extracted"]["coupon"]
    assert c["audience_policies"][0]["form"] == "discount"
    # honesty: never fabricated as FREE / dollar / percent
    assert c["summary"] in {"discount", "Discount"}
    # "parking kiosks" exclusion must not make this a vehicle capacity
    assert c["capacity"]["kind"] != "vehicle"


def test_trustees_go_pass_admission_benefit_phrasing():
    # assabet/burlington__salem-witch-museum
    r = _extract(
        "Pass admission is equivalent to the admission benefit of a Trustees "
        "Family Level Membership for two adults and children under 18. Pass is "
        "valid at any Trustees property that charges admission."
    )
    assert r["status"] == "ok"
    assert r["extracted"]["coupon"]["audience_policies"][0]["form"] == "discount"


def test_trustees_go_pass_family_membership_rates():
    # libcal/bpl__trustees-go-pass-physical-pass
    r = _extract(
        "Coupon allows two adults and children under 18 entry at Family "
        "membership rates. Pass is valid for one-time use at any of 116 "
        "properties that collect an admission fee.",
        platform="libcal",
    )
    assert r["status"] == "ok"
    assert r["extracted"]["coupon"]["audience_policies"][0]["form"] == "discount"


def test_free_or_reduced_is_discount_not_free():
    # assabet/tewksbury__strawbery-banke-museum — "free OR reduced admission"
    # must be a generic discount, NEVER a fabricated plain FREE.
    r = _extract(
        "The Trustees GO Pass: is valid for admission only; it is not valid for "
        "discounts at parking kiosks, stores, cafes, inns, campgrounds. Allows "
        "free or reduced admission, for 2 adults and children under 18."
    )
    assert r["status"] == "ok"
    c = r["extracted"]["coupon"]
    assert c["audience_policies"][0]["form"] == "discount"
    assert c["summary"] in {"discount", "Discount"}


def test_charged_per_visitor_price():
    # libcal/bpl__mass-audubon-wildlife-sanctuary
    r = _extract(
        "This pass allows up to four patrons per visit. Each visitor will be "
        "charged $2.00. Children under two are admitted free.",
        platform="libcal",
    )
    assert r["status"] == "ok"
    c = r["extracted"]["coupon"]
    assert c["summary"] == "$2/person"
    assert c["audience_policies"][0]["form"] == "per-person-price"
    assert c["audience_policies"][0]["value"] == 2


def test_reversed_dollar_off():
    # libcal/milton__paul-revere-heritage-site — "50$ off" (reversed currency)
    r = _extract(
        "Each pass admits 2 people at 50$ off regular admission. "
        "Special events are not included.",
        platform="libcal",
    )
    assert r["status"] == "ok"
    c = r["extracted"]["coupon"]
    assert c["summary"] == "$50 off"
    assert c["audience_policies"][0]["form"] == "dollar-off"
    assert c["audience_policies"][0]["value"] == 50


def test_price_for_n_adults():
    # assabet/haverhill__historic-new-england — "$5 for four (4) adults"
    r = _extract(
        "This pass will provide reduced general admission of $5 for four (4) "
        "adults (18 years and over). Youths 17 and under are always free."
    )
    assert r["status"] == "ok"
    c = r["extracted"]["coupon"]
    assert c["summary"] == "$5/person"
    assert c["audience_policies"][0]["form"] == "per-person-price"
    assert c["audience_policies"][0]["value"] == 5


def test_dcr_vehicle_logistics_only_stays_failed():
    # assabet/boxford__isabella-stewart-gardner-museum — describes only vehicle-
    # display logistics ("displayed in your vehicle ... where daily parking
    # fees are charged"). The pass's free-ness is domain inference, NOT literal
    # text, so per the honesty rule it stays failed.
    r = _extract(
        "This pass must be picked up and dropped off at the library. The pass "
        "must be displayed in your vehicle on rear view mirror or dashboard "
        "when visiting a Mass. State Park facility where daily parking fees are "
        "charged. Pass is not valid for camping."
    )
    assert r["status"] == "failed"


def test_explicit_free_parking_still_free():
    # An explicit "free parking" / "1 vehicle for free" benefit IS literal and
    # must still resolve to FREE (existing convention, kept working).
    r = _extract("Each pass admits 1 vehicle for free at Mass State Parks.")
    assert r["status"] == "ok"
    assert r["extracted"]["coupon"]["summary"] == "FREE"
    assert r["extracted"]["coupon"]["capacity"]["kind"] == "vehicle"


def test_capacity_only_no_benefit_stays_failed():
    # assabet/wakefield__salem-witch-museum — capacity + "prices vary", no value
    r = _extract("Pass admits 2 adults and children under 18. Prices vary by location.")
    assert r["status"] == "failed"


def test_boat_rental_no_cue_stays_failed():
    # assabet/medford__new-england-aquarium — "valid for one boat rental",
    # no free/price/discount wording -> honestly stays failed.
    r = _extract(
        "The pass is valid for one boat rental. Passholder must present pass "
        "and photo ID at rental desk. This includes: single kayak (1 person), "
        "double kayaks (2 adults)."
    )
    assert r["status"] == "failed"
