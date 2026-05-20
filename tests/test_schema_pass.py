from malibbene.schema.pass_ import (
    Pass, PassForm, Coupon, Capacity, CapacityKind,
    AudiencePolicy, CouponForm, Restrictions, EligibilityOverride,
)
from malibbene.schema.library import PassPickupPolicy

def test_coupon_form_enum_includes_bogo():
    assert {e.value for e in CouponForm} == {
        "free", "percent-off", "dollar-off",
        "per-person-price", "bogo", "discount",
    }

def test_capacity_kind_enum():
    assert {e.value for e in CapacityKind} == {"people", "vehicle", "ticket", "unspecified"}

def test_pass_form_enum():
    assert {e.value for e in PassForm} == {"digital_email", "physical_circ", "physical_coupon"}

def test_pass_minimum():
    p = Pass(
        library_id="wakefield",
        attraction_slug="mfa",
        pass_form=PassForm.DIGITAL_EMAIL,
        coupon=Coupon(
            capacity=Capacity(kind=CapacityKind.PEOPLE, n=4),
            audience_policies=[AudiencePolicy(audience="Everyone", form=CouponForm.PERCENT_OFF, value=50)],
        ),
    )
    assert p.available_at_branches == "all"
    assert p.eligibility_override is None
    assert p.restrictions is None

def test_eligibility_override_carries_residency():
    eo = EligibilityOverride(residency=PassPickupPolicy.TOWN_RESIDENT, reason="town park funding")
    assert eo.residency == PassPickupPolicy.TOWN_RESIDENT

def test_restrictions_blackout_uses_month_day():
    r = Restrictions(blackout=[{"month": 7, "day": 4}])
    assert r.blackout[0]["month"] == 7
