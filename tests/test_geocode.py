"""Test Nominatim geocoding wrapper: cache + rate limit + fallback."""
import json
from unittest.mock import patch

from malibbene.common import geocode
from malibbene.common.geocode import haversine_miles


def test_geocode_cache_hit(tmp_path):
    cache_path = tmp_path / "geocache.json"
    cache_path.write_text(json.dumps({
        "1 Science Park, Boston, MA 02114": {"lat": 42.3676, "lon": -71.0712, "ok": True}
    }), encoding="utf-8")

    result = geocode.geocode("1 Science Park, Boston, MA 02114", cache_path=cache_path)
    assert result == {"lat": 42.3676, "lon": -71.0712, "ok": True}


def test_geocode_hits_nominatim_on_cache_miss(tmp_path):
    cache_path = tmp_path / "geocache.json"
    fake_response = json.dumps([{"lat": "42.3676", "lon": "-71.0712"}]).encode()

    with patch("malibbene.common.geocode._urlopen") as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = fake_response
        result = geocode.geocode("Wakefield, MA", cache_path=cache_path)

    assert result["ok"] is True
    assert abs(result["lat"] - 42.3676) < 1e-4
    cached = json.loads(cache_path.read_text(encoding="utf-8"))
    assert "Wakefield, MA" in cached


def test_geocode_records_failure(tmp_path):
    cache_path = tmp_path / "geocache.json"
    with patch("malibbene.common.geocode._urlopen") as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = b"[]"
        result = geocode.geocode("nonexistent place xyz", cache_path=cache_path)

    assert result["ok"] is False
    cached = json.loads(cache_path.read_text(encoding="utf-8"))
    assert cached["nonexistent place xyz"]["ok"] is False


def test_geocode_transient_error_not_cached(tmp_path):
    """Network errors should NOT poison the cache — a later run can retry."""
    cache_path = tmp_path / "geocache.json"

    with patch("malibbene.common.geocode._urlopen", side_effect=Exception("connection refused")):
        result = geocode.geocode("some address", cache_path=cache_path)

    assert result["ok"] is False
    assert "transient" in result["error"]
    # Cache must NOT have this entry — transient errors are not sticky
    if cache_path.exists():
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        assert "some address" not in cached


def test_geocode_corrupt_cache_treated_as_empty(tmp_path):
    """If the cache file is malformed JSON, start fresh instead of crashing."""
    cache_path = tmp_path / "geocache.json"
    cache_path.write_text("{not json", encoding="utf-8")

    fake_response = json.dumps([{"lat": "42.0", "lon": "-71.0"}]).encode()
    with patch("malibbene.common.geocode._urlopen") as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = fake_response
        result = geocode.geocode("anywhere", cache_path=cache_path)

    assert result["ok"] is True


def test_geocode_haversine_distance():
    # Boston to Wakefield, MA ~10 mi straight line
    d = haversine_miles(42.3601, -71.0589, 42.5065, -71.0759)
    assert 9 < d < 13


def test_geocode_haversine_zero_distance():
    assert haversine_miles(42.0, -71.0, 42.0, -71.0) < 0.001


def test_geocode_all_writes_geojson(tmp_path, monkeypatch):
    """End-to-end: read attractions index + library addresses, write geo.json."""
    import json
    import sys
    from pathlib import Path

    structured = tmp_path / "data" / "structured"
    structured.mkdir(parents=True)
    (structured / "_tmp_attractions_index.json").write_text(json.dumps({
        "mos": {"slug": "mos", "address": "1 Science Park, Boston, MA 02114"},
        "_meta": {"n_attractions": 1},  # should be skipped
    }), encoding="utf-8")

    libaddr = tmp_path / "data" / "raw" / "library_addresses"
    libaddr.mkdir(parents=True)
    (libaddr / "wakefield.json").write_text(json.dumps({
        "lib_id": "wakefield", "status": "ok",
        "street": "60 Main Street", "city": "Wakefield", "state": "MA", "zip": "01880",
    }), encoding="utf-8")
    (libaddr / "tewksbury.json").write_text(json.dumps({
        "lib_id": "tewksbury", "status": "failed:no_html_fetched",
    }), encoding="utf-8")
    (libaddr / "_fetch_log.json").write_text(json.dumps({}), encoding="utf-8")  # ignored

    from malibbene.common import geocode as gmod

    def fake_geocode(query, **kw):
        return {"ok": True, "lat": 42.0 + len(query) * 0.001, "lon": -71.0}

    monkeypatch.setattr(gmod, "geocode", fake_geocode)
    import scripts.geocode_all as ga
    monkeypatch.setattr(ga, "REPO", tmp_path)
    ga.main()

    out = json.loads((tmp_path / "data" / "structured" / "geo.json").read_text(encoding="utf-8"))
    assert "mos" in out["attractions"]
    assert "_meta" not in out["attractions"]  # skipped from index
    assert "wakefield" in out["libraries"]
    assert out["attractions"]["mos"]["ok"] is True
    # tewksbury (failed library) should appear with ok=False, not crash
    assert out["libraries"]["tewksbury"]["ok"] is False


def test_geocode_all_skips_files_starting_with_underscore(tmp_path, monkeypatch):
    """_fetch_log.json must not be processed as a library record."""
    import json
    import sys
    from pathlib import Path

    structured = tmp_path / "data" / "structured"
    structured.mkdir(parents=True)
    (structured / "_tmp_attractions_index.json").write_text(json.dumps({}), encoding="utf-8")

    libaddr = tmp_path / "data" / "raw" / "library_addresses"
    libaddr.mkdir(parents=True)
    (libaddr / "_fetch_log.json").write_text(json.dumps({"foo": "bar"}), encoding="utf-8")

    from malibbene.common import geocode as gmod
    monkeypatch.setattr(gmod, "geocode", lambda q, **kw: {"ok": True, "lat": 0, "lon": 0})
    import scripts.geocode_all as ga
    monkeypatch.setattr(ga, "REPO", tmp_path)
    ga.main()

    out = json.loads((tmp_path / "data" / "structured" / "geo.json").read_text(encoding="utf-8"))
    assert "_fetch_log" not in out["libraries"]
