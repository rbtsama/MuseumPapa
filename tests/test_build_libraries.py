"""Test build_libraries: merge seeds + addresses + geo into final libraries.json."""


def test_build_libraries_merges_address_and_geo():
    from malibbene.build.libraries import build_libraries

    seeds = {
        "libraries": [
            {"id": "wakefield", "name": "Lucius Beebe Memorial Library",
             "town": "Wakefield", "network": "NOBLE", "platform": "assabet",
             "card_page": "https://www.wakefieldlibrary.org/get-a-card/",
             "non_resident_policy_initial": "open_ma_resident",
             "supports_availability": True}
        ]
    }
    addresses = {
        "wakefield": {"lib_id": "wakefield", "status": "ok",
                       "street": "60 Main Street", "city": "Wakefield",
                       "state": "MA", "zip": "01880"}
    }
    geo = {"libraries": {"wakefield": {"ok": True, "lat": 42.5065, "lon": -71.0759}}}

    libs = build_libraries(seeds, addresses, geo)

    assert len(libs["libraries"]) == 1
    w = libs["libraries"][0]
    assert w["id"] == "wakefield"
    assert w["town"] == "Wakefield"
    assert w["address"]["street"] == "60 Main Street"
    assert w["address"]["zip"] == "01880"
    assert w["geo"]["lat"] == 42.5065
    assert w["eligibility"] == "open_ma_resident"


def test_build_libraries_handles_missing_address_and_geo():
    from malibbene.build.libraries import build_libraries

    seeds = {
        "libraries": [
            {"id": "tewksbury", "name": "Tewksbury Public Library", "town": "Tewksbury",
             "platform": "assabet", "network": "MVLC",
             "card_page": "https://www.tewksburypl.org/",
             "non_resident_policy_initial": "open_ma_resident",
             "supports_availability": True}
        ]
    }
    libs = build_libraries(seeds, addresses={}, geo={"libraries": {}})

    t = libs["libraries"][0]
    assert t["address"] is None
    assert t["geo"] is None
    assert t["id"] == "tewksbury"


def test_build_libraries_skips_failed_address_status():
    """If address record has status != 'ok', the address field should be None (don't ship partial)."""
    from malibbene.build.libraries import build_libraries
    seeds = {"libraries": [{"id": "x", "name": "X", "town": "X", "platform": "assabet",
                              "network": "X", "card_page": "", "non_resident_policy_initial": "x",
                              "supports_availability": False}]}
    addresses = {"x": {"lib_id": "x", "status": "failed:no_html_fetched",
                       "street": None, "city": None}}
    libs = build_libraries(seeds, addresses, geo={"libraries": {}})
    assert libs["libraries"][0]["address"] is None


def test_build_libraries_includes_meta_summary():
    from malibbene.build.libraries import build_libraries
    seeds = {"libraries": []}
    out = build_libraries(seeds, addresses={}, geo={"libraries": {}})
    assert "_meta" in out
    assert out["_meta"]["n_libraries"] == 0
    assert "built_at" in out["_meta"]
    assert out["_meta"]["n_with_address"] == 0
    assert out["_meta"]["n_with_geo"] == 0
