"""Test build_passes: flatten (lib × attraction) matrix with coupon + calendar."""


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
    assert w["availability"]["2026-05-13"] == "available"
    r = by_lib["reading"]
    assert r["pass_type"] == "physical-coupon"


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


def test_unknown_pass_type_backfills_from_pickup_method_and_raw():
    """When pass_type is unknown but pickup_method is classified, derive pass_type."""
    from malibbene.build.passes import build_passes

    catalog = {"libraries": {
        "cambridge": {"passes": {
            "x-digital": {"pass_type": "unknown", "pass_type_raw": "",
                           "benefit_label": "Free", "benefit_class": "free",
                           "benefits_text": "Pass admits 4 people for free.",
                           "source_url": ""},
            "y-pickup":  {"pass_type": "unknown", "pass_type_raw": "",
                           "benefit_label": "Free", "benefit_class": "free",
                           "benefits_text": "Pick up your pass at the Main Library.",
                           "source_url": ""},
            "z-return":  {"pass_type": "unknown", "pass_type_raw": "",
                           "benefit_label": "Free", "benefit_class": "free",
                           "benefits_text": "Pick up at the library and return next day.",
                           "source_url": ""},
        }}
    }}
    classifications = {"cambridge": {
        "x-digital": {"pass_id": "x-digital", "pickup_method": "digital",               "pickup_branches": []},
        "y-pickup":  {"pass_id": "y-pickup",  "pickup_method": "physical_at_branch",     "pickup_branches": ["cambridge--main"]},
        "z-return":  {"pass_id": "z-return",  "pickup_method": "physical_at_branch",     "pickup_branches": ["cambridge--main"]},
    }}
    branches_doc = {"branches": [{"id": "cambridge--main", "parent_lib_id": "cambridge",
                                   "name": "Cambridge Main", "address": {}, "geo": {}, "hours_raw": None}]}
    out = build_passes(catalog, classifications=classifications, branches_doc=branches_doc)
    by_slug = {p["attraction_slug"]: p for p in out["passes"]}
    assert by_slug["x-digital"]["pass_type"] == "digital"
    assert by_slug["y-pickup"]["pass_type"] == "physical-coupon"
    assert by_slug["z-return"]["pass_type"] == "physical-circ"


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
