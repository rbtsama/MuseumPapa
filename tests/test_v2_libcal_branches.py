from pathlib import Path

from malibbene.sources_v2.libcal.branches import (
    parse_bpl_locations,
    parse_brookline_locations,
    parse_cambridge_locations,
)


def test_parse_bpl_locations_returns_at_least_15_branches():
    # BPL's www.bpl.org/locations/ page is JS-rendered (BiblioCommons widget).
    # The actual data source used by that page is the BiblioCommons gateway JSON
    # endpoint, which is what we parse here. See branches.py for details.
    body = (Path(__file__).parent / "fixtures/libcal/bpl_branches.json").read_text(
        encoding="utf-8"
    )
    branches = parse_bpl_locations(body)
    assert len(branches) >= 15
    assert any(b["name"].lower().startswith("brighton") for b in branches)
    assert all("id" in b and "name" in b for b in branches)


def test_parse_cambridge_locations():
    body = (
        Path(__file__).parent / "fixtures/libcal/cambridge_locations.html"
    ).read_text(encoding="utf-8")
    branches = parse_cambridge_locations(body)
    # Main + 6 neighborhood branches (Boudreau, Central Square, Collins,
    # O'Connell, O'Neill, Valente).
    assert len(branches) >= 5
    names = {b["name"] for b in branches}
    assert "Main Library" in names
    assert any("Boudreau" in n for n in names)
    for b in branches:
        assert b["library_id"] == "cambridge"
        assert b["id"].startswith("cambridge-")
        assert b["name"]


def test_parse_brookline_locations():
    body = (
        Path(__file__).parent / "fixtures/libcal/brookline_locations.html"
    ).read_text(encoding="utf-8")
    branches = parse_brookline_locations(body)
    assert len(branches) == 3
    names = {b["name"] for b in branches}
    assert names == {"Brookline Village", "Coolidge Corner", "Putterham"}
    for b in branches:
        assert b["library_id"] == "brookline"
        assert b["id"].startswith("brookline-")
