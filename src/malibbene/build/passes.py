from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, timezone
from malibbene.common.audit_overrides import load_overrides, apply_overrides
from malibbene.build.slug_canonical import canonical
from malibbene.build.coupons import coupon_from_extract, restrictions_from_extract, coupon_coverage_gaps

PLATFORMS = ("assabet","libcal","museumkey")

# Authoritative pass-type (scraped deterministically from the index page) ->
# the schema's pass_form. `unknown` and anything unmapped return None so the
# caller keeps the legacy/default value.
_PASS_TYPE_TO_FORM = {
    "digital": "digital_email",
    "physical-coupon": "physical_coupon",
    "physical-circ": "physical_circ",
}

def _pass_form_from_pass_type(pass_type: str | None) -> str | None:
    return _PASS_TYPE_TO_FORM.get(pass_type)

def _read(p): return json.loads(p.read_text()) if p.exists() else None

def _index_pass_types(raw_root: Path, platform: str, lib: str) -> dict:
    """slug -> pass_type from the index/ snapshot for one library (empty if absent).

    The index/ files carry deterministic pass_type for all 59 libraries; the v2
    catalog scraper only began emitting pass_type after the markup fix, so this
    snapshot is the authoritative source until catalog/ is re-scraped.
    """
    idx = _read(raw_root / platform / "index" / f"{lib}.json")
    if not idx:
        return {}
    return {p.get("slug"): p.get("pass_type") for p in idx.get("passes", []) if p.get("slug")}

def build_passes(raw_root: Path, overrides_root: Path, out_path: Path) -> dict:
    overrides = load_overrides(overrides_root)
    out_passes = []
    for platform in PLATFORMS:
        catalog_dir = raw_root / platform / "catalog"
        if not catalog_dir.exists(): continue
        for cat_f in catalog_dir.glob("*.json"):
            cat = json.loads(cat_f.read_text())
            lib = cat["library_id"]
            idx_pass_types = _index_pass_types(raw_root, platform, lib)
            for p in cat.get("passes",[]):
                # `rawslug` is the catalog slug used to KEY the raw coupon /
                # availability / probe files (look those up with it). The
                # emitted row carries the CANONICAL slug so it joins to one
                # attraction record. The 405KB top-level `source_phrases` blob
                # is dropped (bloat) — coupon.source_phrase_block keeps the
                # meaningful provenance.
                rawslug = p["attraction_slug"]
                slug = canonical(rawslug)
                row = {
                    "library_id": lib, "attraction_slug": slug,
                    "attraction_rawslug": rawslug,  # build's override key; panel uses this for pass targets
                    "pass_form": "physical_coupon",
                    "available_at_branches": "all",
                    "source_url": p.get("detail_url"),
                    "coupon": None, "restrictions": None,
                    # The real booking filter. Defaults to unknown — silence in
                    # catalog text does NOT mean the pass is open to non-residents
                    # (the platform may enforce residency at reservation time).
                    # Filled from explicit text here, or from a booking probe.
                    "residency_restriction": {
                        "restricted": "unknown", "scope": None,
                        "source": None, "evidence": None,
                    },
                    "availability": {},
                    "eligibility_override": None,
                }
                # pass_form, residency, and legacy coupon fallback from the original
                # per-platform extraction. Its coupon VALUES are stale/often wrong, so
                # only trust it for pass_form/residency and as a last-resort fallback.
                old = _read(raw_root/platform/"coupons"/f"{lib}__{rawslug}.json")
                old_e = old["extracted"] if (old and old.get("status") == "ok") else None
                if old_e:
                    row["pass_form"] = old_e.get("pass_form", "physical_coupon")
                    if old_e.get("residency_restriction"):
                        row["residency_restriction"] = old_e["residency_restriction"]
                # AUTHORITATIVE pass_form: the deterministic pass_type scraped from
                # the index page (catalog record first, else the index/ snapshot)
                # overrides the LLM-guessed legacy old_e value. Unknown -> keep prior.
                pf = _pass_form_from_pass_type(p.get("pass_type") or idx_pass_types.get(rawslug))
                if pf:
                    row["pass_form"] = pf
                # AUTHORITATIVE coupon numbers: data/raw/pass_coupons/<lib>_<canonical>.json
                # (single underscore, canonical slug, top-level fields). Canonical name
                # first, then raw-slug name, then the legacy extraction as fallback.
                crec = (_read(raw_root/"pass_coupons"/f"{lib}_{slug}.json")
                        or _read(raw_root/"pass_coupons"/f"{lib}_{rawslug}.json"))
                if crec and crec.get("status") == "ok":
                    row["coupon"] = coupon_from_extract(crec)
                    # crec is authoritative for the coupon AND its restrictions;
                    # the stale legacy old_e is only a fallback when crec has none (B2).
                    row["restrictions"] = restrictions_from_extract(crec) or (old_e or {}).get("restrictions")
                elif old_e:
                    row["coupon"] = old_e.get("coupon")
                    row["restrictions"] = old_e.get("restrictions")
                # A booking-probe result (Phase P3) tests the TOWN-residency axis
                # (can a same-network non-resident book it). It takes precedence,
                # EXCEPT it must not erase a text-derived MA-resident requirement
                # (a different axis the probe can't test, since the prober is
                # itself a MA resident).
                probe = _read(raw_root/platform/"residency_probe"/f"{lib}__{rawslug}.json")
                if probe and probe.get("restricted") in ("yes", "no"):
                    text_rr = row.get("residency_restriction") or {}
                    text_is_ma = (text_rr.get("restricted") == "yes"
                                  and text_rr.get("scope") == "ma")
                    if probe["restricted"] == "no" and text_is_ma:
                        # Town-open confirmed by probe, but the catalog text still
                        # requires a MA resident in the party — keep that, annotate.
                        row["residency_restriction"] = {
                            "restricted": "yes", "scope": "ma",
                            "source": "catalog_text+booking_probe",
                            "evidence": (text_rr.get("evidence") or "")
                            + " | booking probe: town-open (non-town same-network card accepted)",
                        }
                    else:
                        row["residency_restriction"] = {
                            "restricted": probe["restricted"],
                            "scope": probe.get("scope"),
                            "source": "booking_probe",
                            "evidence": probe.get("evidence"),
                        }
                avail = _read(raw_root/platform/"availability"/lib/f"{rawslug}.json")
                if avail:
                    row["availability"] = {d["date"]:d["status"] for d in avail.get("days",[])}
                key = f"{lib}__{rawslug}"
                row = apply_overrides(f"pass:{key}", row, overrides)
                out_passes.append(row)
    # Silent-drop guard: refuse to ship if any pass has an empty coupon while an
    # authoritative pass_coupons file exists for it (the bug this fix addresses).
    gaps = coupon_coverage_gaps(out_passes, raw_root)
    if gaps:
        raise ValueError(
            f"coupon coverage regression: {len(gaps)} pass(es) shipped an empty coupon "
            f"despite an authoritative data/raw/pass_coupons file existing — e.g. {gaps[:8]}. "
            f"Check the pass_coupons path/slug lookup in build_passes."
        )
    n_with_coupon = sum(1 for p in out_passes if p.get("coupon"))
    out = {"_meta":{"built_at":datetime.now(timezone.utc).isoformat(),
                    "n_passes":len(out_passes),
                    "n_with_coupon":n_with_coupon,
                    "coupon_coverage_pct":round(100*n_with_coupon/max(1,len(out_passes)),1)},
           "passes": out_passes}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    return out
