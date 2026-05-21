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


# --- new card-eligibility patterns (real text snippets encountered in scrape) ---

def test_card_open_anyone_eligible():
    # Wakefield (Lucius Beebe Memorial Library) get-a-card page.
    text = ("Anyone is eligible for a library card with valid identification and "
            "proof of current address (e.g. a driver's license and utility bill).")
    assert classify_card_eligibility(text) == CardEligibility.MA_RESIDENT


def test_card_anyone_can_get_card():
    # Peabody Institute Library.
    text = "How can I get a Library Card? Anyone can get a Peabody Institute Library card at any of our 3 locations!"
    assert classify_card_eligibility(text) == CardEligibility.MA_RESIDENT


def test_card_any_ma_resident_may_register():
    # Saugus Public Library.
    text = "Any Massachusetts resident may register and use any public library in the Commonwealth."
    assert classify_card_eligibility(text) == CardEligibility.MA_RESIDENT


def test_card_resident_of_massachusetts():
    # Malden Public Library.
    text = ("To apply for a library card, you do not have to be a resident of "
            "Malden, but you do have to be a resident of Massachusetts.")
    assert classify_card_eligibility(text) == CardEligibility.MA_RESIDENT


def test_card_massachusetts_residency_required():
    # Winchester Public Library.
    text = "Massachusetts residency is required to get your library card."
    assert classify_card_eligibility(text) == CardEligibility.MA_RESIDENT


def test_card_available_to_all_town_residents():
    # Flint Memorial Library (North Reading) — two-word town.
    text = "A library card is available to all North Reading residents. To obtain a card, you will need a photo ID."
    assert classify_card_eligibility(text) == CardEligibility.TOWN_RESIDENT


def test_card_residents_of_town_proper():
    # Wilmington Memorial Library.
    text = "Residents of Wilmington Proper identification is required to apply for a Wilmington Memorial Library (WML) card."
    assert classify_card_eligibility(text) == CardEligibility.TOWN_RESIDENT


def test_card_residents_of_commonwealth():
    text = "Library cards are free to residents of the Commonwealth of Massachusetts."
    assert classify_card_eligibility(text) == CardEligibility.MA_RESIDENT


# --- honesty guards: real noise that must NOT classify -------------------------

def test_card_service_announcement_does_not_match_town():
    # Boxford homepage — a streaming-service blurb, not card eligibility.
    text = "Hoopla Digital is Now Available to Boxford Residents! Boxford Town Library card holders can now access Hoopla."
    assert classify_card_eligibility(text) == CardEligibility.UNKNOWN


def test_card_streaming_residents_only_does_not_match():
    # Goodnow Library (Sudbury) homepage — "residents only" is a Hoopla caveat.
    text = ("Create an account with your library card number. Sudbury residents only.\n"
            "Kanopy is an on-demand streaming video service.")
    assert classify_card_eligibility(text) == CardEligibility.UNKNOWN


def test_card_bare_work_does_not_match_town_or_works():
    # A lone "work" / "apply" in event prose must not trigger town_or_works.
    text = "Apply to be the next Kid Librarian! Bring your handwork to the Reference Room."
    assert classify_card_eligibility(text) == CardEligibility.UNKNOWN


def test_card_menu_link_network_does_not_match():
    # Lawrence homepage menu: "MVLC & BPL E-cards" is a nav link, not a policy.
    text = "Library Card Services\nLibrary Card Application\nMVLC & BPL E-cards\nBooks & Online Resources"
    assert classify_card_eligibility(text) == CardEligibility.UNKNOWN


# --- new pass-pickup patterns --------------------------------------------------

def test_pickup_ma_resident_tied_to_pass():
    # Saugus pass page.
    text = "Pass Benefits 50% off admission price. Visitors must be Massachusetts residents to use this pass."
    assert classify_pass_pickup(text) == PassPickupPolicy.MA_RESIDENT


def test_pickup_town_resident_tied_to_pass():
    # Winchester pass page.
    text = "Passes are available to Winchester residents only. A household may reserve passes."
    assert classify_pass_pickup(text) == PassPickupPolicy.TOWN_RESIDENT


def test_pickup_museum_admission_residents_does_not_match():
    # Cambridge pass page: a museum's own free-Sunday admission, not pickup policy.
    text = ("Harvard Museums of Science & Culture are free to Massachusetts residents "
            "every Sunday morning year-round.")
    assert classify_pass_pickup(text) == PassPickupPolicy.UNKNOWN
