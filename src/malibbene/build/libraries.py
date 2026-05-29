from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, timezone
from malibbene.common.audit_overrides import load_overrides, apply_overrides
from malibbene.build.legacy import legacy_libraries

def _load_town_zips(seed_path: Path) -> dict:
    """Load config/town_zips.json (sibling of the seed file). Returns town->[zip5]."""
    zips_path = seed_path.parent / "town_zips.json"
    if not zips_path.exists():
        print(f"WARNING: {zips_path} not found — resident_zips will be empty for all libraries")
        return {}
    return json.loads(zips_path.read_text(encoding="utf-8")).get("towns", {})


def build_libraries(seed_path: Path, raw_root: Path, overrides_root: Path, out_path: Path) -> dict:
    seeds = json.loads(seed_path.read_text())
    if isinstance(seeds, dict):
        seeds = seeds["libraries"]
    overrides = load_overrides(overrides_root)
    town_zips = _load_town_zips(seed_path)
    # The 2026-05-20 rebuild dropped geo/address for all libraries. Recover them
    # from the legacy archive (59/59). Seed values, if any, take precedence;
    # audit overrides (applied below) win over both.
    legacy = legacy_libraries()
    libs = []
    for s in seeds:
        leg = legacy.get(s["id"], {})
        lib = {
            "id": s["id"], "name": s["name"], "town": s["town"],
            "network": s["network"], "platform": s["platform"],
            "consortium_label": s.get("consortium_label", s["network"]),
            "card_issuance_group": s.get("card_issuance_group", s["network"]),
            "card_issuance_groups": list(s.get("card_issuance_groups") or [s.get("card_issuance_group", s["network"])]),
            "card_auth_groups": list(s.get("card_auth_groups") or [s["network"]]),
            "card_page": s.get("card_page"),
            "address": s.get("address") or leg.get("address"),
            "geo": s.get("geo") or leg.get("geo"),
            "card_eligibility": "unknown",
            "pass_pickup_default": "unknown",
        }
        zips = town_zips.get(s["town"])
        if not zips:
            print(f"WARNING: no resident_zips for town {s['town']!r} (library {s['id']})")
        lib["resident_zips"] = list(zips or [])
        policies_path = raw_root / s["platform"] / "policies" / f"{s['id']}.json"
        if policies_path.exists():
            pol = json.loads(policies_path.read_text())
            if pol.get("card_page"):
                lib["card_eligibility"] = pol["card_page"].get("card_eligibility","unknown")
            if pol.get("pass_page"):
                lib["pass_pickup_default"] = pol["pass_page"].get("pass_pickup","unknown")
            # NOTE: eligibility_source_phrase / pickup_source_phrase dropped — the
            # raw policy_text is scraped nav-menu / schema.org noise (67/118 garbage),
            # not real provenance. Re-add only with a proper policy-text extractor.
        lib = apply_overrides(f"library:{s['id']}", lib, overrides)
        # Overlay verbatim card-eligibility source block (plan: source-block
        # extraction). data/raw/libraries/_source_blocks/<id>.json. A null
        # card_eligibility is honest "no passage found" — skipped, not invented.
        sb_path = raw_root / "libraries" / "_source_blocks" / f"{s['id']}.json"
        if sb_path.exists():
            sb = json.loads(sb_path.read_text(encoding="utf-8"))
            ce = sb.get("card_eligibility")
            if ce and ce.get("source_block"):
                lib.setdefault("_evidence", {})["card_eligibility"] = {
                    "evidence": ce.get("source_phrase"),
                    "block": ce.get("source_block"),
                    "source": ce.get("source_url"),
                    "source_confidence": ce.get("source_confidence"),
                }
        libs.append(lib)
    out = {
        "_meta": {"built_at": datetime.now(timezone.utc).isoformat(),"n_libraries": len(libs)},
        "libraries": libs,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    return out
