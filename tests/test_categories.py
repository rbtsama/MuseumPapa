from __future__ import annotations

from malibbene.build.categories import CANONICAL, canonicalize


def test_canonical_names_roundtrip_through_canonicalize():
    """Every canonical category, when fed back in as raw input, must survive.

    Legacy attractions.json stores already-canonical names (e.g. 'Performance').
    Re-running canonicalize on them must not silently drop any — a missing
    self-map is why Performance went to 0 attractions.
    """
    for name in CANONICAL:
        assert canonicalize([name]) == [name], f"{name} dropped by canonicalize"


def test_performance_self_map():
    assert canonicalize(["Performance"]) == ["Performance"]
