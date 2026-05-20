from malibbene.schema.library import Library, CardEligibility, PassPickupPolicy

def test_card_eligibility_enum_has_six_values():
    assert {e.value for e in CardEligibility} == {
        "ma_resident", "town_resident", "town_or_works",
        "network", "none", "unknown",
    }

def test_pass_pickup_enum_has_eight_values():
    assert {e.value for e in PassPickupPolicy} == {
        "same_as_card", "ma_resident", "town_resident",
        "town_cardholder_only", "network",
        "walkin_for_nonresidents", "none", "unknown",
    }

def test_library_minimum_required_fields():
    lib = Library(
        id="wakefield", name="Lucius Beebe Memorial Library",
        town="Wakefield", network="NOBLE", platform="assabet",
        card_eligibility=CardEligibility.MA_RESIDENT,
        pass_pickup_default=PassPickupPolicy.SAME_AS_CARD,
    )
    assert lib.id == "wakefield"
    assert lib.branch_ids == []
