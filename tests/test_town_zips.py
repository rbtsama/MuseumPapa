"""Validate config/town_zips.json against the 59 library towns.

Honesty contract: every library town must map to a non-empty real ZIP5 list
(or be explicitly parked in _uncertain). No guessed ZIPs.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CONFIG = REPO / "config"

ZIP5 = re.compile(r"^\d{5}$")


def _load_town_zips() -> dict:
    return json.loads((CONFIG / "town_zips.json").read_text(encoding="utf-8"))


def _library_towns() -> list[str]:
    seeds = json.loads((CONFIG / "library_seeds.json").read_text(encoding="utf-8"))
    return [lib["town"] for lib in seeds["libraries"]]


def test_every_library_town_is_mapped_or_uncertain() -> None:
    data = _load_town_zips()
    towns = data["towns"]
    uncertain = set(data.get("_uncertain", []))
    missing = []
    for town in set(_library_towns()):
        entry = towns.get(town)
        if entry:  # non-empty list
            continue
        if town in uncertain:
            continue
        missing.append(town)
    assert not missing, f"library towns with no town_zips entry and not in _uncertain: {sorted(missing)}"


def test_all_zips_are_five_digit_strings() -> None:
    towns = _load_town_zips()["towns"]
    for town, zips in towns.items():
        assert isinstance(zips, list), f"{town} value is not a list"
        for z in zips:
            assert isinstance(z, str) and ZIP5.match(z), f"{town}: bad ZIP5 {z!r}"


def test_no_duplicate_zips_within_a_town() -> None:
    towns = _load_town_zips()["towns"]
    for town, zips in towns.items():
        assert len(zips) == len(set(zips)), f"{town} has duplicate ZIPs"


def test_wakefield_maps_to_01880() -> None:
    towns = _load_town_zips()["towns"]
    assert towns["Wakefield"] == ["01880"]
