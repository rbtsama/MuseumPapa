from __future__ import annotations
import json
import time
import hashlib
from pathlib import Path
from datetime import datetime
from collections import Counter
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from malibbene.build.slug_canonical import canonical
from malibbene.build.passes import infer_pass_form_from_text

def _pct(n,total): return round(100.0*n/total,1) if total else 0.0


REPO = Path(__file__).resolve().parents[3]
DEFAULT_SOURCE_URL_CACHE = REPO / "data" / ".cache" / "source_url_status.json"
DEFAULT_SOURCE_URL_TTL_SECONDS = 72 * 3600


def _parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def check_build_consistency(out_dir: Path, max_skew_seconds: int = 3600) -> None:
    """Raise if the structured files were not built in the same run.

    build_all writes all four within seconds; a large skew in _meta.built_at
    means one file (usually passes.json) was rebuilt alone and the products are
    out of sync (the B5 finding: passes was 3 days newer than the rest)."""
    stamps = {}
    for name in ("libraries", "attractions", "branches", "passes"):
        p = out_dir / f"{name}.json"
        if not p.exists():
            continue
        built = (json.loads(p.read_text()).get("_meta") or {}).get("built_at")
        if built:
            stamps[name] = _parse_ts(built)
    if len(stamps) < 2:
        return
    skew = (max(stamps.values()) - min(stamps.values())).total_seconds()
    if skew > max_skew_seconds:
        newest = max(stamps, key=stamps.get); oldest = min(stamps, key=stamps.get)
        raise ValueError(
            f"structured files built {skew/3600:.1f}h apart — not one build run "
            f"({newest} @ {stamps[newest].isoformat()} vs {oldest} @ {stamps[oldest].isoformat()}). "
            f"Run scripts/build_all.py to rebuild them together."
        )


def _referential_integrity(libs, attrs, passes) -> None:
    """Raise ValueError on structural corruption: a pass pointing at a
    library_id or attraction_slug that does not exist, or a duplicate
    (library_id, attraction_slug) pair. These are never acceptable to ship —
    slug_canonical passes unknown slugs through unchanged, so a typo or new
    platform would otherwise create a silent orphan row."""
    lib_ids = {l.get("id") for l in libs}
    attr_slugs = {a.get("slug") for a in attrs}
    orphan_lib = sorted({p.get("library_id") for p in passes if p.get("library_id") not in lib_ids})
    orphan_attr = sorted({p.get("attraction_slug") for p in passes if p.get("attraction_slug") not in attr_slugs})
    pairs = Counter((p.get("library_id"), p.get("attraction_slug")) for p in passes)
    dup_pairs = sorted(k for k, n in pairs.items() if n > 1)
    problems = []
    if orphan_lib:
        problems.append(f"{len(orphan_lib)} pass(es) reference an unknown library: {orphan_lib[:8]}")
    if orphan_attr:
        problems.append(f"{len(orphan_attr)} pass(es) reference an unknown attraction: {orphan_attr[:8]}")
    if dup_pairs:
        problems.append(f"{len(dup_pairs)} duplicate (library, attraction) pair(s): {dup_pairs[:8]}")
    if problems:
        raise ValueError("referential integrity failed:\n  " + "\n  ".join(problems))


def _duplicate_audience_count(passes) -> int:
    """Passes whose coupon lists the same (audience, age_range) more than once.
    A data-quality smell (e.g. paid Child + free-infant Child sharing a key) —
    reported, not fatal."""
    n = 0
    for p in passes:
        aps = (p.get("coupon") or {}).get("audience_policies") or []
        keys = [(a.get("audience"), json.dumps(a.get("age_range"), sort_keys=True)) for a in aps]
        if len(keys) != len(set(keys)):
            n += 1
    return n

def _libcal_catalog_texts(raw_root: Path | None) -> dict[tuple[str, str], str]:
    if not raw_root:
        return {}
    out = {}
    catalog_dir = raw_root / "libcal" / "catalog"
    if not catalog_dir.exists():
        return out
    for cat_f in catalog_dir.glob("*.json"):
        cat = json.loads(cat_f.read_text(encoding="utf-8"))
        lib = cat.get("library_id")
        for p in cat.get("passes", []):
            rawslug = p.get("attraction_slug")
            if not lib or not rawslug:
                continue
            out[(lib, canonical(rawslug))] = p.get("benefit_text") or ""
    return out

def _pass_form_catalog_conflicts(passes, raw_root: Path | None) -> tuple[int, list[dict]]:
    texts = _libcal_catalog_texts(raw_root)
    mismatches = []
    for p in passes:
        text = texts.get((p.get("library_id"), p.get("attraction_slug")))
        if not text:
            continue
        expected = infer_pass_form_from_text(text)
        actual = p.get("pass_form")
        if expected and actual and expected != actual:
            mismatches.append({
                "library_id": p.get("library_id"),
                "attraction_slug": p.get("attraction_slug"),
                "expected": expected,
                "actual": actual,
            })
    return len(mismatches), mismatches[:8]


def _booking_probe_own_card_conflicts(passes) -> tuple[int, list[dict]]:
    mismatches = []
    for p in passes:
        rr = p.get("residency_restriction") or {}
        evidence = " ".join(filter(None, [p.get("own_card_evidence"), rr.get("evidence")])).lower()
        if not evidence:
            continue

        expects_own = "blocked at card-validation" in evidence or "card rejected" in evidence
        expects_open = "same-network card accepted" in evidence or "card accepted" in evidence
        actual_own = bool(p.get("requires_own_card"))

        if rr.get("source") == "booking_probe_card_ownership" and rr.get("restricted") != "no":
            mismatches.append({
                "library_id": p.get("library_id"),
                "attraction_slug": p.get("attraction_slug"),
                "issue": "booking_probe_card_ownership_must_not_set_residency_block",
                "actual_restricted": rr.get("restricted"),
            })
            continue

        if expects_own and not actual_own:
            mismatches.append({
                "library_id": p.get("library_id"),
                "attraction_slug": p.get("attraction_slug"),
                "issue": "probe_blocked_but_requires_own_card_false",
            })
        elif expects_open and actual_own:
            mismatches.append({
                "library_id": p.get("library_id"),
                "attraction_slug": p.get("attraction_slug"),
                "issue": "probe_accepted_but_requires_own_card_true",
            })
    return len(mismatches), mismatches[:8]

def fetch_url_status(url: str, timeout: int = 10) -> int | None:
    req = Request(url, headers={"User-Agent": "MuseumPapa validate/1.0"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            return getattr(resp, "status", None) or resp.getcode()
    except HTTPError as e:
        return e.code
    except URLError:
        return None


def _load_status_cache(cache_path: Path) -> dict[str, dict]:
    if not cache_path.exists():
        return {}
    try:
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(cached, dict):
        return {}
    return cached


def _save_status_cache(cache_path: Path, cache: dict[str, dict]) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache, indent=2, sort_keys=True), encoding="utf-8")


def _cache_key(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()


def build_source_url_fetcher(
    *,
    fetcher=fetch_url_status,
    cache_path: Path = DEFAULT_SOURCE_URL_CACHE,
    ttl_seconds: int = DEFAULT_SOURCE_URL_TTL_SECONDS,
    now: float | None = None,
):
    clock = time.time if now is None else (lambda: now)
    cache = _load_status_cache(cache_path)

    def cached_fetch(url: str) -> int | None:
        key = _cache_key(url)
        entry = cache.get(key)
        if entry and entry.get("url") == url:
            checked_at = entry.get("checked_at")
            if isinstance(checked_at, (int, float)) and clock() - checked_at <= ttl_seconds:
                return entry.get("status")

        status = fetcher(url)
        if status is None:
            return None

        cache[key] = {"url": url, "status": status, "checked_at": clock()}
        _save_status_cache(cache_path, cache)
        return status

    return cached_fetch

def _source_url_health(passes, fetcher=None) -> tuple[int | None, list[dict]]:
    if fetcher is None:
        return None, []
    seen = {}
    bad = []
    for p in passes:
        url = p.get("source_url")
        if not url:
            continue
        if url not in seen:
            seen[url] = fetcher(url)
        status = seen[url]
        if status is not None and status >= 400:
            bad.append({
                "library_id": p.get("library_id"),
                "attraction_slug": p.get("attraction_slug"),
                "status": status,
                "source_url": url,
            })
    return len(bad), bad[:8]

def validate_build(
    libraries: Path,
    attractions: Path,
    passes_file: Path,
    *,
    raw_root: Path | None = None,
    source_url_fetcher=None,
) -> dict:
    libs = json.loads(libraries.read_text())["libraries"]
    attrs = json.loads(attractions.read_text())["attractions"]
    passes = json.loads(passes_file.read_text())["passes"]

    # Hard gate: corruption must never ship.
    _referential_integrity(libs, attrs, passes)

    pass_form_conflict_count, pass_form_conflict_samples = _pass_form_catalog_conflicts(passes, raw_root)
    booking_probe_conflict_count, booking_probe_conflict_samples = _booking_probe_own_card_conflicts(passes)
    dead_source_url_count, dead_source_url_samples = _source_url_health(passes, source_url_fetcher)

    return {
        "libraries": {
            "n": len(libs),
            "card_eligibility_unknown_pct": _pct(
                sum(1 for l in libs if l.get("card_eligibility")=="unknown"), len(libs)),
            "pass_pickup_unknown_pct": _pct(
                sum(1 for l in libs if l.get("pass_pickup_default")=="unknown"), len(libs)),
        },
        "attractions": {
            "n": len(attrs),
            "visitor_eligibility_missing_pct": _pct(
                sum(1 for a in attrs if not a.get("visitor_eligibility")), len(attrs)),
            "reservation_missing_pct": _pct(
                sum(1 for a in attrs if not a.get("reservation")), len(attrs)),
            # Data-quality (non-fatal): attractions that ended up with no category
            # filter out of every category browse.
            "empty_categories_count":
                sum(1 for a in attrs if not (a.get("categories") or [])),
        },
        "passes": {
            "n": len(passes),
            "coupon_missing_pct": _pct(
                sum(1 for p in passes if not p.get("coupon")), len(passes)),
            "duplicate_audience_count": _duplicate_audience_count(passes),
            "pass_form_catalog_conflict_count": pass_form_conflict_count,
            "pass_form_catalog_conflict_samples": pass_form_conflict_samples,
            "booking_probe_own_card_conflict_count": booking_probe_conflict_count,
            "booking_probe_own_card_conflict_samples": booking_probe_conflict_samples,
            "dead_source_url_count": dead_source_url_count,
            "dead_source_url_samples": dead_source_url_samples,
        },
    }
