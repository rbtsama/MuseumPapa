from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, timezone
from malibbene.common.audit_overrides import load_overrides, apply_overrides
from malibbene.common.geocode import geocode, haversine_miles

# A geocoded branch must sit within this radius of its library's centroid, else
# we drop the coordinate. Nominatim will happily resolve a branch name ("Central",
# "Brighton") to a same-named place in another state; the radius guard rejects
# those so the UI never shows a wildly wrong pickup distance. A null geo is
# honest ("we don't know where this branch is") and the UI degrades gracefully.
MAX_BRANCH_MILES = 20.0


def accept_geo(result: dict, lib_geo: dict | None, max_mi: float = MAX_BRANCH_MILES) -> dict | None:
    """Return {lat, lon} when a geocode hit is usable, else None.

    Usable = the lookup succeeded AND (no library centroid to check against, OR
    the hit is within ``max_mi`` of that centroid). Pure function — unit-tested
    offline so the risky "is this hit plausible" logic doesn't need the network.
    """
    if not result.get("ok"):
        return None
    lat, lon = result["lat"], result["lon"]
    if lib_geo and lib_geo.get("lat") is not None:
        if haversine_miles(lib_geo["lat"], lib_geo["lon"], lat, lon) > max_mi:
            return None
    return {"lat": lat, "lon": lon}


def _geocode_branch(name: str, town: str, lib_geo: dict | None) -> dict | None:
    """Geocode one branch by name. Tries a library-qualified query first, then a
    looser one; returns the first hit that passes ``accept_geo`` or None."""
    for q in (f"{name} Branch Library, {town}, MA", f"{name}, {town}, MA"):
        geo = accept_geo(geocode(q), lib_geo)
        if geo:
            return geo
    return None


def build_branches(raw_root: Path, overrides_root: Path, out_path: Path,
                   libraries_path: Path | None = None) -> dict:
    branches_dir = raw_root/"libcal"/"branches"
    overrides = load_overrides(overrides_root)

    # Library centroid + town feed the geocode query and the sanity radius.
    # Defaults to the libraries.json sibling so a standalone run still works
    # (build_all builds libraries.json before branches).
    if libraries_path is None:
        libraries_path = out_path.parent/"libraries.json"
    libs: dict[str, dict] = {}
    if Path(libraries_path).exists():
        for lib in json.loads(Path(libraries_path).read_text(encoding="utf-8")).get("libraries", []):
            libs[lib["id"]] = lib

    out_branches = []
    n_geo = 0
    if branches_dir.exists():
        for f in sorted(branches_dir.glob("*.json")):
            data = json.loads(f.read_text(encoding="utf-8"))
            for b in data.get("branches", []):
                lib = libs.get(b["library_id"], {})
                town = lib.get("town") or (lib.get("address") or {}).get("city") or "Boston"
                # Don't re-geocode if a coordinate is already present (e.g. an
                # override supplied one). Otherwise look it up (cached on disk).
                if not b.get("geo"):
                    b["geo"] = _geocode_branch(b["name"], town, lib.get("geo"))
                if b.get("geo"):
                    n_geo += 1
                key = f"{b['library_id']}__{b['id'].replace(b['library_id']+'-','')}"
                b = apply_overrides(f"branch:{key}", b, overrides)
                out_branches.append(b)

    out = {"_meta": {"built_at": datetime.now(timezone.utc).isoformat(),
                    "n_branches": len(out_branches),
                    "n_geocoded": n_geo},
           "branches": out_branches}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    return out
