"""Offline tests for the branch-geo sanity guard (no network).

``accept_geo`` is the risky bit of branch geocoding — it decides whether a
Nominatim hit is plausible enough to keep. We test it in isolation so the
"reject a same-named place in another state" logic is verified without hitting
the network.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from malibbene.build.branches import accept_geo

# BPL Copley centroid.
BPL = {"lat": 42.3493, "lon": -71.0787}


def test_failed_lookup_returns_none():
    assert accept_geo({"ok": False, "error": "no_results"}, BPL) is None


def test_hit_within_radius_is_kept():
    # East Boston branch — ~3 mi from Copley, well inside the guard.
    geo = accept_geo({"ok": True, "lat": 42.3778, "lon": -71.0281}, BPL)
    assert geo == {"lat": 42.3778, "lon": -71.0281}


def test_hit_outside_radius_is_dropped():
    # A "Central" somewhere in Connecticut — must be rejected, not shown as a
    # bogus pickup distance.
    assert accept_geo({"ok": True, "lat": 41.7658, "lon": -72.6734}, BPL) is None


def test_no_library_centroid_keeps_any_hit():
    # With nothing to check against we can't validate distance — keep the hit.
    geo = accept_geo({"ok": True, "lat": 10.0, "lon": 20.0}, None)
    assert geo == {"lat": 10.0, "lon": 20.0}
