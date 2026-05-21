from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, timezone
from malibbene.common.audit_overrides import load_overrides, apply_overrides

PLATFORMS = ("assabet","libcal","museumkey")

def _read(p): return json.loads(p.read_text()) if p.exists() else None

def build_passes(raw_root: Path, overrides_root: Path, out_path: Path) -> dict:
    overrides = load_overrides(overrides_root)
    out_passes = []
    for platform in PLATFORMS:
        catalog_dir = raw_root / platform / "catalog"
        if not catalog_dir.exists(): continue
        for cat_f in catalog_dir.glob("*.json"):
            cat = json.loads(cat_f.read_text())
            lib = cat["library_id"]
            for p in cat.get("passes",[]):
                slug = p["attraction_slug"]
                row = {
                    "library_id": lib, "attraction_slug": slug,
                    "pass_form": "physical_coupon",
                    "available_at_branches": "all",
                    "source_url": p.get("detail_url"),
                    "source_phrases": p.get("source_phrases",[]),
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
                coup = _read(raw_root/platform/"coupons"/f"{lib}__{slug}.json")
                if coup and coup.get("status")=="ok":
                    e = coup["extracted"]
                    row["pass_form"] = e.get("pass_form","physical_coupon")
                    row["coupon"] = e.get("coupon")
                    row["restrictions"] = e.get("restrictions")
                    if e.get("residency_restriction"):
                        row["residency_restriction"] = e["residency_restriction"]
                # A booking-probe result (Phase P3) tests the TOWN-residency axis
                # (can a same-network non-resident book it). It takes precedence,
                # EXCEPT it must not erase a text-derived MA-resident requirement
                # (a different axis the probe can't test, since the prober is
                # itself a MA resident).
                probe = _read(raw_root/platform/"residency_probe"/f"{lib}__{slug}.json")
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
                avail = _read(raw_root/platform/"availability"/lib/f"{slug}.json")
                if avail:
                    row["availability"] = {d["date"]:d["status"] for d in avail.get("days",[])}
                key = f"{lib}__{slug}"
                row = apply_overrides(f"pass:{key}", row, overrides)
                out_passes.append(row)
    out = {"_meta":{"built_at":datetime.now(timezone.utc).isoformat(),
                    "n_passes":len(out_passes)}, "passes": out_passes}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    return out
