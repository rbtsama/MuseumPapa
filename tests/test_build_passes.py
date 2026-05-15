"""Test build_passes: flatten (lib × attraction) matrix with discount + calendar."""


def test_build_passes_flattens_lib_x_attraction():
    from malibbene.build.passes import build_passes

    catalog = {
        "libraries": {
            "wakefield": {
                "passes": {
                    "mos": {"pass_type": "digital", "benefit_label": "Free",
                            "benefit_class": "free", "benefits_text": "Free for 4 people",
                            "source_url": "https://wakefieldlibrary.assabetinteractive.com/pass/mos",
                            "pass_type_raw": "Digital coupon",
                            "calendar": {"2026-05-13": "available", "2026-05-14": "booked"}}
                }
            },
            "reading": {
                "passes": {
                    "mos": {"pass_type": "physical-coupon", "benefit_label": "50% off",
                            "benefit_class": "half", "benefits_text": "Half price for 4",
                            "source_url": "https://readingpl.assabetinteractive.com/pass/mos",
                            "pass_type_raw": "Coupon (pick up at library)",
                            "calendar": {}}
                }
            }
        }
    }

    out = build_passes(catalog)

    assert len(out["passes"]) == 2
    by_lib = {p["library_id"]: p for p in out["passes"]}
    w = by_lib["wakefield"]
    assert w["attraction_slug"] == "mos"
    assert w["pass_type"] == "digital"
    assert w["discount"]["class"] == "free"
    assert w["discount"]["label"] == "Free"
    assert w["discount"]["raw"] == "Free for 4 people"
    assert w["availability"]["2026-05-13"] == "available"
    r = by_lib["reading"]
    assert r["pass_type"] == "physical-coupon"
    assert r["discount"]["class"] == "half"


def test_build_passes_handles_missing_calendar():
    """A pass without calendar key (or empty calendar) should set availability=None."""
    from malibbene.build.passes import build_passes
    catalog = {"libraries": {"x": {"passes": {"y": {"pass_type": "digital",
                                                      "benefit_label": "Free",
                                                      "benefit_class": "free",
                                                      "benefits_text": "",
                                                      "source_url": "",
                                                      "pass_type_raw": ""}}}}}
    out = build_passes(catalog)
    assert out["passes"][0]["availability"] is None


def test_build_passes_meta_counts():
    from malibbene.build.passes import build_passes
    out = build_passes({"libraries": {}})
    assert out["_meta"]["n_passes"] == 0
    assert out["_meta"]["n_with_availability"] == 0
    assert "built_at" in out["_meta"]


def test_build_passes_counts_with_availability():
    """Passes with non-empty calendar count toward n_with_availability."""
    from malibbene.build.passes import build_passes
    catalog = {"libraries": {
        "a": {"passes": {"x": {"pass_type": "digital", "benefit_label": "Free",
                                "benefit_class": "free", "benefits_text": "", "source_url": "",
                                "pass_type_raw": "", "calendar": {"2026-05-13": "available"}}}},
        "b": {"passes": {"x": {"pass_type": "digital", "benefit_label": "Free",
                                "benefit_class": "free", "benefits_text": "", "source_url": "",
                                "pass_type_raw": ""}}},
    }}
    out = build_passes(catalog)
    assert out["_meta"]["n_passes"] == 2
    assert out["_meta"]["n_with_availability"] == 1
