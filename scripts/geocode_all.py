"""Geocode all attractions + libraries; write data/structured/geo.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

import re

from malibbene.common import geocode as gmod

# Address tokens Nominatim chokes on — strip before sending
_NOISE_TOKENS = [
    r"\bSuite\s+\d+[A-Z]?\b",
    r"\bUnit\s+[A-Z0-9]+\b",
    r"\bBuilding\s+\d+\b",
    r"\bSte\.?\s+\d+[A-Z]?\b",
    r"\bAdministrative Offices:[^,]*",
    r"\bSeifert Performing Arts Center\b",
    r"\bOdiorne Point State Park\b",
    r"\bCharlestown Navy Yard\b",
]


def _clean_address(addr: str) -> str:
    for pat in _NOISE_TOKENS:
        addr = re.sub(pat, "", addr, flags=re.IGNORECASE)
    # "297-321 East Street" → "297 East Street" (Nominatim wants a single number)
    addr = re.sub(r"\b(\d+)\s*-\s*\d+\b", r"\1", addr)
    addr = re.sub(r",\s*,", ",", addr)
    addr = re.sub(r"\s+", " ", addr).strip(", ")
    return addr


def _clean_name(name: str) -> str:
    name = re.sub(r"\s*\(.*?\)\s*", " ", name)  # drop parens
    name = name.split("/")[0]  # "X/Y" → "X"
    return re.sub(r"\s+", " ", name).strip()


def _attraction_queries(entry: dict) -> list[str]:
    """Yield candidate geocode queries in priority order."""
    queries: list[str] = []
    addr = (entry.get("address") or "").strip()
    if addr:
        queries.append(addr)
        cleaned = _clean_address(addr)
        if cleaned and cleaned != addr:
            queries.append(cleaned)
    name = (entry.get("museum_name") or "").strip()
    if name:
        queries.append(f"{name}, Massachusetts, USA")
        queries.append(name)
        clean = _clean_name(name)
        if clean and clean != name:
            queries.append(f"{clean}, Massachusetts, USA")
            queries.append(clean)
    # Dedup preserving order
    seen: set[str] = set()
    out: list[str] = []
    for q in queries:
        if q not in seen:
            seen.add(q)
            out.append(q)
    return out


def _library_query(addr_record: dict) -> str | None:
    if addr_record.get("status") != "ok":
        return None
    parts = [addr_record.get("street"), addr_record.get("city"),
             addr_record.get("state"), addr_record.get("zip")]
    parts = [p for p in parts if p]
    return ", ".join(parts) if parts else None


def main() -> int:
    structured = REPO / "data" / "structured"
    idx_path = structured / "_tmp_attractions_index.json"
    if not idx_path.exists():
        print("ERROR: run scripts/build_attractions_index.py first", file=sys.stderr)
        return 1

    attractions_idx = json.loads(idx_path.read_text(encoding="utf-8"))
    libaddr_dir = REPO / "data" / "raw" / "library_addresses"

    out: dict = {"attractions": {}, "libraries": {}}

    # Attractions
    n_ok = 0
    n_attr = 0
    for slug, entry in attractions_idx.items():
        if slug.startswith("_"):
            continue  # _meta etc.
        n_attr += 1
        queries = _attraction_queries(entry)
        if not queries:
            out["attractions"][slug] = {"ok": False, "error": "no_address_or_name"}
            continue
        result: dict = {"ok": False, "error": "no_results"}
        for q in queries:
            r = gmod.geocode(q)
            if r.get("ok"):
                result = r
                result["query"] = q
                break
            result = r
        out["attractions"][slug] = result
        if result.get("ok"):
            n_ok += 1
    print(f"Attractions: {n_ok}/{n_attr} geocoded")

    # Libraries
    n_ok = 0
    n_total = 0
    if libaddr_dir.exists():
        for f in sorted(libaddr_dir.glob("*.json")):
            if f.name.startswith("_"):
                continue  # _fetch_log.json
            n_total += 1
            rec = json.loads(f.read_text(encoding="utf-8"))
            q = _library_query(rec)
            if not q:
                out["libraries"][f.stem] = {"ok": False, "error": "no_address"}
                continue
            r = gmod.geocode(q)
            out["libraries"][f.stem] = r
            if r.get("ok"):
                n_ok += 1
    print(f"Libraries: {n_ok}/{n_total} geocoded")

    (structured / "geo.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Wrote {structured / 'geo.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
