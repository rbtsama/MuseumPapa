import json
from pathlib import Path


def test_all_seeds_have_required_fields():
    data = json.loads(
        (Path(__file__).resolve().parent.parent / "config/library_seeds.json").read_text(encoding="utf-8")
    )
    seeds = data["libraries"] if isinstance(data, dict) else data
    for s in seeds:
        assert "id" in s and "name" in s and "town" in s
        assert "network" in s and "platform" in s
        assert "card_page" in s
        assert "pass_page" in s  # may be null but must exist
        if s["platform"] == "libcal":
            assert s.get("libcal_base"), f"{s['id']} missing libcal_base"
        if s["id"] in ("bpl",):  # only BPL has a working parser
            assert s.get("locations_url"), f"{s['id']} missing locations_url"
        if s["platform"] == "museumkey":
            assert "base_url" in s, f"{s['id']} missing base_url field"
