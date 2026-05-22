import json
from pathlib import Path

from malibbene.testgame.select import (
    select_sample,
    SAMPLE_LIB_IDS,
    SAMPLE_ATTRACTION_SLUGS,
    EXTRA_TOWNS,
)

REPO = Path(__file__).resolve().parents[1]
STRUCT = REPO / "data" / "structured"


def _load():
    libs = json.loads((STRUCT / "libraries.json").read_text(encoding="utf-8"))["libraries"]
    attrs = json.loads((STRUCT / "attractions.json").read_text(encoding="utf-8"))["attractions"]
    passes = json.loads((STRUCT / "passes.json").read_text(encoding="utf-8"))["passes"]
    return libs, attrs, passes


def test_sample_sizes_and_real():
    sample = select_sample(*_load())
    assert len(sample["libraries"]) == len(SAMPLE_LIB_IDS) == 9
    assert len(sample["attractions"]) == len(SAMPLE_ATTRACTION_SLUGS) == 7
    assert {l["id"] for l in sample["libraries"]} == set(SAMPLE_LIB_IDS)
    assert {a["slug"] for a in sample["attractions"]} == set(SAMPLE_ATTRACTION_SLUGS)


def test_networks_span_five():
    sample = select_sample(*_load())
    nets = {l["network"] for l in sample["libraries"]}
    assert {"NOBLE", "Minuteman", "MVLC", "MBLN", "OCLN"} <= nets


def test_towns_include_in_and_out_of_range():
    sample = select_sample(*_load())
    assert set(EXTRA_TOWNS) <= set(sample["towns"])
    assert "Lexington" in sample["towns"]
    lib_towns = {l["town"] for l in sample["libraries"]}
    assert all(t not in lib_towns for t in EXTRA_TOWNS)


def test_blithewold_is_state4_anchor():
    sample = select_sample(*_load())
    blith = [p for p in sample["passes"] if p["attraction_slug"] == "blithewold"]
    assert len(blith) == 1
    assert any(p["library_id"] == "lexington" for p in blith)
    assert any(p["residency"] == "yes" for p in blith)


def test_no_fabrication_summary_passthrough():
    sample = select_sample(*_load())
    for p in sample["passes"]:
        assert p["summary"] is None or (isinstance(p["summary"], str) and p["summary"])
        assert p["residency"] in {"yes", "no", "unknown"}


def test_pass_records_have_required_fields():
    sample = select_sample(*_load())
    assert sample["passes"], "应至少有若干 pass"
    for p in sample["passes"]:
        for k in ("library_id", "attraction_slug", "network", "library_name", "library_town", "residency", "summary"):
            assert k in p
        assert p["library_id"] in SAMPLE_LIB_IDS
        assert p["attraction_slug"] in SAMPLE_ATTRACTION_SLUGS


def test_booking_url_is_absolute_or_none():
    sample = select_sample(*_load())
    for a in sample["attractions"]:
        url = a["booking_url"]
        assert url is None or url.startswith("http"), f"{a['slug']} booking_url not absolute: {url!r}"
