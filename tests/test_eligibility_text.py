from malibbene.common.eligibility_text import classify_card_eligibility, classify_pass_pickup
from malibbene.schema.library import CardEligibility, PassPickupPolicy

def test_classify_card_ma_resident():
    text = "Library cards are available to all Massachusetts residents at no charge."
    assert classify_card_eligibility(text) == CardEligibility.MA_RESIDENT

def test_classify_card_town_only():
    text = "Cards are available to Wakefield residents only with proof of residency."
    assert classify_card_eligibility(text) == CardEligibility.TOWN_RESIDENT

def test_classify_card_town_or_works():
    text = "Available to those who live, work, or attend school in Acton."
    assert classify_card_eligibility(text) == CardEligibility.TOWN_OR_WORKS

def test_classify_card_unknown_when_no_hint():
    text = "We welcome you to the library. Hours are 10-8."
    assert classify_card_eligibility(text) == CardEligibility.UNKNOWN

def test_pickup_walkin_for_nonresidents():
    text = "Wakefield residents may reserve passes online. Non-residents are welcome for same-day walk-in only."
    assert classify_pass_pickup(text) == PassPickupPolicy.WALKIN_FOR_NONRESIDENTS

def test_pickup_town_cardholder_only():
    text = "Museum passes are reserved for patrons holding a Cohasset library card."
    assert classify_pass_pickup(text) == PassPickupPolicy.TOWN_CARDHOLDER_ONLY
