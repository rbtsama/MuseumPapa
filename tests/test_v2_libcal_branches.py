from pathlib import Path

from malibbene.sources_v2.libcal.branches import parse_bpl_locations


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
