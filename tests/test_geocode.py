"""Test Nominatim geocoding wrapper: cache + rate limit + fallback."""
import json
from unittest.mock import patch


def test_geocode_cache_hit(tmp_path):
    from malibbene.common import geocode

    cache_path = tmp_path / "geocache.json"
    cache_path.write_text(json.dumps({
        "1 Science Park, Boston, MA 02114": {"lat": 42.3676, "lon": -71.0712, "ok": True}
    }), encoding="utf-8")

    result = geocode.geocode("1 Science Park, Boston, MA 02114", cache_path=cache_path)
    assert result == {"lat": 42.3676, "lon": -71.0712, "ok": True}


def test_geocode_hits_nominatim_on_cache_miss(tmp_path):
    from malibbene.common import geocode

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
    from malibbene.common import geocode

    cache_path = tmp_path / "geocache.json"
    with patch("malibbene.common.geocode._urlopen") as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = b"[]"
        result = geocode.geocode("nonexistent place xyz", cache_path=cache_path)

    assert result["ok"] is False
    cached = json.loads(cache_path.read_text(encoding="utf-8"))
    assert cached["nonexistent place xyz"]["ok"] is False


def test_geocode_haversine_distance():
    from malibbene.common.geocode import haversine_miles
    # Boston to Wakefield, MA ~12mi straight line
    d = haversine_miles(42.3601, -71.0589, 42.5065, -71.0759)
    assert 9 < d < 13


def test_geocode_haversine_zero_distance():
    from malibbene.common.geocode import haversine_miles
    assert haversine_miles(42.0, -71.0, 42.0, -71.0) < 0.001
