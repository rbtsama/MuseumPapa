"""Nominatim (OSM) geocoding wrapper: cache + rate limit + haversine.

Nominatim usage policy: max 1 req/sec, required User-Agent identifying the app.
See https://operations.osmfoundation.org/policies/nominatim/
"""
from __future__ import annotations

import json
import math
import time
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
DEFAULT_CACHE = REPO / "data" / ".cache" / "geocode.json"
UA = "MuseumPass-MA-Geocoder/0.1 (https://github.com/rbtsama)"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_LAST_REQUEST_AT = 0.0


def _urlopen(req, timeout=30):
    """Indirection so tests can patch this without touching urllib globals."""
    return urllib.request.urlopen(req, timeout=timeout)


def _rate_limit() -> None:
    """Sleep so consecutive calls are at least 1.05s apart (Nominatim policy)."""
    global _LAST_REQUEST_AT
    elapsed = time.time() - _LAST_REQUEST_AT
    if elapsed < 1.05:
        time.sleep(1.05 - elapsed)
    _LAST_REQUEST_AT = time.time()


def _load_cache(cache_path: Path) -> dict:
    if not cache_path.exists():
        return {}
    try:
        return json.loads(cache_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _save_cache(cache_path: Path, cache: dict) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")


def geocode(query: str, *, cache_path: Path = DEFAULT_CACHE) -> dict:
    """Geocode a free-form address; return {lat, lon, ok} or {ok: False, error}.

    Successful results and 'no_results' (semantic miss) are persisted to
    ``cache_path``. Network / parse errors are returned but NOT cached, so a
    later run after the transient issue passes will retry.
    """
    cache = _load_cache(cache_path)
    if query in cache:
        return cache[query]

    _rate_limit()
    qs = urllib.parse.urlencode({"q": query, "format": "json", "limit": 1})
    req = urllib.request.Request(f"{NOMINATIM_URL}?{qs}", headers={"User-Agent": UA})
    try:
        with _urlopen(req, timeout=30) as resp:
            body = resp.read()
        results = json.loads(body)
    except Exception as e:
        # Transient failure — do NOT cache, so a future run can retry.
        return {"ok": False, "error": f"transient:{e}"}

    if not results:
        entry = {"ok": False, "error": "no_results"}
    else:
        entry = {"ok": True, "lat": float(results[0]["lat"]), "lon": float(results[0]["lon"])}

    cache[query] = entry
    _save_cache(cache_path, cache)
    return entry


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Straight-line great-circle distance in miles."""
    R_MILES = 3958.8
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R_MILES * math.asin(math.sqrt(a))
