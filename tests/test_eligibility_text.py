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


# --- patterns from JS-rendered card pages (Phase O) ----------------------------

def test_card_live_in_a_massachusetts_town():
    # Lynnfield (NOBLE eCard) — "live in a Massachusetts town" must be ma_resident.
    text = ("You are eligible to apply for a NOBLE eCard if you live in a Massachusetts "
            "town and do not currently have a library card from a NOBLE member library.")
    assert classify_card_eligibility(text) == CardEligibility.MA_RESIDENT


def test_card_residents_of_any_ma_community():
    # NOBLE/network phrasing: residents of any Massachusetts community.
    text = "An eCard is available to residents of any Massachusetts community without a NOBLE card."
    assert classify_card_eligibility(text) == CardEligibility.MA_RESIDENT


def test_card_proof_of_local_address_is_town_resident():
    # Acton Memorial Library — requires proof of current local address.
    text = ("To get a library card you must show photo identification and proof of current "
            "local address. If an applicant is under 13 years old, a parent must be present.")
    assert classify_card_eligibility(text) == CardEligibility.TOWN_RESIDENT


def test_card_id_and_address_no_scope_stays_unknown():
    # Stoneham — only "ID and a document with your current address", no residency
    # scope stated. Honest outcome: UNKNOWN (we do not invent a scope).
    text = ("In order to register for a Stoneham Public Library card in person, you must "
            "bring a form of ID and/or another document with your current address to the desk.")
    assert classify_card_eligibility(text) == CardEligibility.UNKNOWN


# --- patterns from JS-rendered card pages (Phase O round 2) --------------------

def test_card_regardless_of_where_you_live_in_ma():
    # Lynnfield (lynnfieldlibrary.org/about/get-a-library-card/) — full-access card.
    text = ("Library cards are free and available regardless of where you live in "
            "Massachusetts. In addition to the above information, proof of current "
            "mailing address (license, checkbook, utility bill, etc.) is needed.")
    assert classify_card_eligibility(text) == CardEligibility.MA_RESIDENT


def test_card_anyone_who_lives_in_ma_or_works_in_town():
    # Acton Memorial Library (actonmemoriallibrary.org/services/library-cards/).
    text = ("Library cards are available to anyone 4 years and older who lives in "
            "Massachusetts or works in Acton. Anyone who would like a full service "
            "library card must apply in person at the Circulation Desk.")
    assert classify_card_eligibility(text) == CardEligibility.MA_RESIDENT


def test_card_any_town_resident_is_eligible():
    # Boxford Town Library (boxfordma.gov/210/Get-a-Library-Card).
    text = ("Any Boxford Resident is eligible to obtain a Boxford Town Library Account "
            "and Card. To obtain an account please follow the steps outlined below.")
    assert classify_card_eligibility(text) == CardEligibility.TOWN_RESIDENT


def test_card_library_card_anyone_can_get_one():
    # Everett Public Libraries (everettpubliclibraries.org/get-a-library-card/).
    text = ("A library card is totally free, and anyone can get one! All you need is "
            "a form of photo I.D. and proof of address.")
    assert classify_card_eligibility(text) == CardEligibility.MA_RESIDENT


def test_card_live_anywhere_in_massachusetts():
    # Chelmsford Public Library (chelmsfordlibrary.org/about/get-a-library-card).
    text = ("If you live anywhere in Massachusetts (including Chelmsford) and do not "
            "already have a card from an MVLC Library, you may apply for a library "
            "card online.")
    assert classify_card_eligibility(text) == CardEligibility.MA_RESIDENT


def test_card_have_a_massachusetts_address():
    # Weston Public Library (official "least exclusive club in Weston" statement).
    text = ("If you have a Massachusetts address, you make the cut. If you don't have "
            "a library card, just visit our Circulation Desk.")
    assert classify_card_eligibility(text) == CardEligibility.MA_RESIDENT


def test_card_current_massachusetts_address_required():
    # Concord Free Public Library — must provide ID with a current MA address.
    text = ("To open a library account, please visit the Circulation Desk and provide "
            "a valid ID with your current Massachusetts address.")
    assert classify_card_eligibility(text) == CardEligibility.MA_RESIDENT


def test_card_negated_live_in_ma_does_not_match_via_that_clause():
    # Concord FAQ heading "I don't live in Massachusetts / I'm just visiting" must
    # NOT, on its own, be read as a live-in-MA eligibility statement (it is the
    # opposite). With no other MA cue this stays UNKNOWN.
    text = ("Out-of-State Cards. I don't live in Massachusetts / I'm just visiting. "
            "Can I still get a card? Out-of-state residents pay an annual fee.")
    assert classify_card_eligibility(text) == CardEligibility.UNKNOWN


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
