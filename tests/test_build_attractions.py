"""Test build_attractions: collect all attractions from catalog + enrich."""


def test_build_attractions_merges_price_image_geo():
    from malibbene.build.attractions import build_attractions

    catalog = {
        "libraries": {
            "wakefield": {
                "passes": {
                    "mos": {"museum_name": "Museum of Science",
                            "address": "1 Science Park, Boston, MA 02114",
                            "website": "https://www.mos.org/",
                            "categories": ["Science", "Family"]}
                }
            },
            "reading": {
                "passes": {
                    "mos": {"museum_name": "Museum of Science",
                            "address": "1 Science Park, Boston, MA 02114",
                            "website": "https://www.mos.org/",
                            "categories": ["Science"]}
                }
            }
        }
    }
    prices = {"mos": {"slug": "mos", "status": "ok",
                       "adult": 33, "child": 28, "youth": 25, "senior": 29, "student": None,
                       "military": 27, "educator": 27,
                       "family": None, "free_under_age": None, "notes": None,
                       "source_url": "https://www.mos.org/visit"}}
    images = {"mos": {"slug": "mos", "status": "ok",
                       "og_image_url": "https://www.mos.org/og.jpg",
                       "local_path": "static/images/mos.jpg"}}
    geo = {"attractions": {"mos": {"ok": True, "lat": 42.367, "lon": -71.071}}}

    out = build_attractions(catalog, prices, images, geo)

    assert len(out["attractions"]) == 1
    a = out["attractions"][0]
    assert a["slug"] == "mos"
    assert a["museum_name"] == "Museum of Science"
    assert set(a["categories"]) == {"Science", "Children"}  # Family/Science → Children/Science via canonicalize
    assert set(a["categories_raw"]) == {"Science", "Family"}  # raw labels preserved
    assert set(a["sources"]) == {"wakefield", "reading"}
    assert a["original_price"]["age_pricing"]["adult"]["price"] == 33
    assert a["original_price"]["age_pricing"]["child"]["price"] == 28
    assert a["original_price"]["age_pricing"]["youth"]["price"] == 25
    assert a["original_price"]["identity_pricing"]["military"]["price"] == 27
    assert a["original_price"]["identity_pricing"]["educator"]["price"] == 27
    assert a["hero_image"]["og_image_url"] == "https://www.mos.org/og.jpg"
    assert a["geo"]["lat"] == 42.367


def test_build_attractions_uses_two_layer_price_schema():
    """Prices are split into age_pricing (age-based) and identity_pricing (status-based)."""
    from malibbene.build.attractions import build_attractions
    catalog = {"libraries": {"wakefield": {"passes": {"mos": {
        "museum_name": "Museum of Science", "address": "1 Science Park, Boston, MA",
        "website": "https://www.mos.org", "categories": ["Science", "Family"],
    }}}}}
    prices = {"mos": {"status": "ok", "adult": 33, "child": 28, "youth": 25,
                       "senior": 30, "student": 27, "military": 0, "educator": 0,
                       "family": None, "free_under_age": 3, "notes": None,
                       "source_url": "https://www.mos.org/admission"}}
    out = build_attractions(catalog, prices, {}, {"attractions": {}}, hours={}, descriptions={})
    p = out["attractions"][0]["original_price"]
    assert p["age_pricing"]["adult"]["price"] == 33
    assert p["age_pricing"]["child"]["price"] == 28
    assert p["age_pricing"]["senior"]["price"] == 30
    assert p["age_pricing"]["free_under_age"] == 3
    assert p["identity_pricing"]["student"]["price"] == 27
    assert p["identity_pricing"]["military"]["price"] == 0
    assert p["identity_pricing"]["educator"]["price"] == 0
    assert "adult" not in p
    assert "student" not in p


def test_build_attractions_surfaces_phone_and_description():
    """phone + description should propagate from catalog pass into attraction."""
    from malibbene.build.attractions import build_attractions
    catalog = {
        "libraries": {
            "wakefield": {
                "passes": {
                    "bcm": {
                        "museum_name": "Boston Children's Museum",
                        "address": "308 Congress St, Boston, MA",
                        "website": "https://bostonchildrensmuseum.org/",
                        "phone": "617-426-6500",
                        "description": "Second oldest children's museum in the US.",
                        "categories": ["Kids"],
                    }
                }
            }
        }
    }
    out = build_attractions(catalog, prices={}, images={}, geo={"attractions": {}})
    a = out["attractions"][0]
    assert a["phone"] == "617-426-6500"
    assert "children's museum" in a["description"].lower()


def test_build_attractions_handles_missing_enrichments():
    from malibbene.build.attractions import build_attractions

    catalog = {
        "libraries": {
            "cohasset": {
                "passes": {
                    "obscure-museum": {"museum_name": "Obscure", "address": "", "website": "",
                                       "categories": ["History"]}
                }
            }
        }
    }
    out = build_attractions(catalog, prices={}, images={}, geo={"attractions": {}})

    a = out["attractions"][0]
    assert a["slug"] == "obscure-museum"
    assert a["original_price"] is None
    assert a["hero_image"] is None
    assert a["geo"] is None


def test_build_attractions_skips_failed_price_status():
    """Price entries with status != ok should produce original_price=None."""
    from malibbene.build.attractions import build_attractions
    catalog = {"libraries": {"x": {"passes": {"y": {"museum_name": "Y", "address": "",
                                                       "website": "", "categories": []}}}}}
    prices = {"y": {"slug": "y", "status": "failed:no_extractable_price",
                     "adult": None, "child": None}}
    out = build_attractions(catalog, prices, {}, {"attractions": {}})
    assert out["attractions"][0]["original_price"] is None


def test_build_attractions_meta():
    from malibbene.build.attractions import build_attractions
    out = build_attractions({"libraries": {}}, {}, {}, {"attractions": {}})
    assert out["_meta"]["n_attractions"] == 0
    assert "built_at" in out["_meta"]
    assert out["_meta"]["n_with_price"] == 0
    assert out["_meta"]["n_with_image"] == 0
    assert out["_meta"]["n_with_geo"] == 0
