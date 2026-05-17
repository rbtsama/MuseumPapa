"""Tests for coupon attachment in build_passes (plan-9 Task 3)."""


def test_build_passes_attaches_coupon():
    from malibbene.build.passes import build_passes
    catalog = {"libraries": {"wakefield": {"passes": {"mos": {
        "pass_type": "digital", "pass_type_raw": "Digital",
        "benefits_text": "Pass admits up to 4 for half price.",
        "source_url": "", "benefit_label": "", "benefit_class": ""
    }}}}}
    coupons = {"wakefield_mos": {
        "status": "ok",
        "capacity": {"kind": "people", "n": 4},
        "audience_policies": [
            {"audience": "Everyone", "age_range": None, "count": None,
             "form": "percent-off", "value": 50}
        ],
        "restrictions": {"blackout_dates": [], "weekdays_only": False,
                         "seasonal": None, "reservation_required": False},
        "raw": "Pass admits up to 4 for half price.",
    }}
    out = build_passes(catalog, coupons=coupons)
    p = out["passes"][0]
    assert p["coupon"]["capacity"]["n"] == 4
    assert p["coupon"]["audience_policies"][0]["form"] == "percent-off"
    assert "discount" not in p
    assert "policy" not in p


def test_build_passes_empty_coupon_when_missing():
    from malibbene.build.passes import build_passes
    catalog = {"libraries": {"x": {"passes": {"y": {
        "pass_type": "digital", "pass_type_raw": "",
        "benefits_text": "", "source_url": "",
        "benefit_label": "", "benefit_class": ""}}}}}
    out = build_passes(catalog, coupons={})
    p = out["passes"][0]
    assert p["coupon"]["capacity"]["kind"] == "unspecified"
    assert p["coupon"]["audience_policies"] == []
    assert p["restrictions"] is None


def test_build_passes_attaches_restrictions_when_any_flag_set():
    from malibbene.build.passes import build_passes
    catalog = {"libraries": {"a": {"passes": {"b": {
        "pass_type": "digital", "pass_type_raw": "",
        "benefits_text": "", "source_url": "",
        "benefit_label": "", "benefit_class": ""}}}}}
    coupons = {"a_b": {"status": "ok",
                       "capacity": {"kind": "unspecified", "n": None},
                       "audience_policies": [
                           {"audience": "Everyone", "age_range": None,
                            "count": None, "form": "free", "value": None}
                       ],
                       "restrictions": {"blackout_dates": ["2026-10-01", "2026-10-31"],
                                        "weekdays_only": False,
                                        "seasonal": None,
                                        "reservation_required": False},
                       "raw": ""}}
    out = build_passes(catalog, coupons=coupons)
    p = out["passes"][0]
    assert p["restrictions"]["blackout_dates"] == ["2026-10-01", "2026-10-31"]
