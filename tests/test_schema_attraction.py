from malibbene.schema.attraction import (
    Attraction, VisitorEligibility, Reservation,
    ReservationRequired, PassHolderPath, AudiencePrice,
)

def test_reservation_required_enum():
    assert {e.value for e in ReservationRequired} == {"none", "timed_entry", "walk_in_ok"}

def test_pass_holder_path_enum():
    assert {e.value for e in PassHolderPath} == {
        "promo_code_in_general_checkout", "dedicated_pass_sku",
        "dedicated_pass_holders_url", "library_only", "unknown",
    }

def test_attraction_construct_minimum():
    a = Attraction(slug="mfa", name="Museum of Fine Arts")
    assert a.slug == "mfa"
    assert a.prices == []
    assert a.visitor_eligibility is None
    assert a.reservation is None

def test_audience_price_fields():
    p = AudiencePrice(audience="adult", price=27.0, source_phrase="Adults $27")
    assert p.audience == "adult"
    assert p.price == 27.0
