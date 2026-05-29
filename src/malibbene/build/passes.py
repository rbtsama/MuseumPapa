from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, timezone
from malibbene.common.audit_overrides import load_overrides, apply_overrides, is_entity_removed
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

def residency_from_coupon(coupon: dict | None) -> tuple[str, str] | None:
    """Detect explicit residents-only language in the coupon's source_phrase_block.

    Returns (scope, evidence) where scope is "town" or "ma", or None when the
    coupon text is silent on residency. This is the AUTHORITATIVE source for
    residency — the probe only tests card scope, never residency policy.
    """
    if not coupon: return None
    block = coupon.get("source_phrase_block","") or ""
    if not block: return None
    import re as _re
    if _re.search(r"\b(massachusetts|MA)\s+residents?\s+only\b", block, _re.I):
        m = _re.search(r"\b(?:massachusetts|MA)\s+residents?\s+only\b", block, _re.I)
        return ("ma", f'coupon source phrase: "{m.group(0)}"')
    PATTERNS = (
        r"\bfor\s+(\w[\w\- ]{2,20})\s+residents?\s+only\b",
        r"\bto\s+(\w[\w\- ]{2,20})\s+residents?\s+only\b",
        r"\bavailable\s+(?:only\s+)?to\s+(\w[\w\- ]{2,20})\s+residents?\b",
        r"\bmust be (?:a|an)\s+(\w[\w\- ]{2,20})\s+resident\b",
        r"\brestricted\s+to\s+(\w[\w\- ]{2,20})\s+residents?\b",
        r"\blimited\s+to\s+(\w[\w\- ]{2,20})\s+residents?\b",
    )
    NOISE = {"ma","massachusetts","library","member","adult","adults","one","children","child"}
    for rx in PATTERNS:
        m = _re.search(rx, block, _re.I)
        if m:
            tok = m.group(1).strip().lower()
            if tok in NOISE: continue
            return ("town", f'coupon source phrase: "{m.group(0).strip()}"')
    return None


def infer_pass_form_from_text(text: str | None) -> str | None:
    t = " ".join((text or "").lower().split())
    if not t:
        return None
    if "digital (downloadable via email)" in t or "e-coupon" in t or "e-ticket" in t:
        return "digital_email"
    # These explicit no-return cues are more trustworthy than the generic
    # LibCal footer boilerplate that sometimes still says "picked up ... and
    # returned" even when the pass page body says otherwise.
    if "does not need to be returned" in t or "this is a disposable pass" in t or "disposable pass" in t:
        return "physical_coupon"
    if "returnable pass" in t or "must be returned" in t:
        return "physical_circ"
    if "physical passes must be picked up" in t or "must be picked up at the branch" in t or "must be picked up at the library" in t:
        return "physical_coupon"
    return None

def _detail_hex(url: str | None) -> str | None:
    if not url:
        return None
    return url.rstrip("/").rsplit("/", 1)[-1] or None

def _index_pass_types(raw_root: Path, platform: str, lib: str) -> tuple[dict, dict]:
    """Return (slug_map, hex_map) from the index/ snapshot for one library.

    The index/ files carry deterministic pass_type for all 59 libraries; the v2
    catalog scraper only began emitting pass_type after the markup fix, so this
    snapshot is the authoritative source until catalog/ is re-scraped.
    """
    idx = _read(raw_root / platform / "index" / f"{lib}.json")
    if not idx:
        return {}, {}
    slug_map = {}
    hex_map = {}
    for p in idx.get("passes", []):
        raw = p.get("slug")
        pass_type = p.get("pass_type")
        if raw:
            slug_map[raw] = pass_type
            # LibCal often emits slightly different catalog vs index slugs
            # ("...-theatre" vs "...-theater", "...-tours", "...-physical-pass").
            # The canonical attraction slug is the stable join key, so expose it as
            # a second lookup path for pass_form recovery.
            slug_map[canonical(raw)] = pass_type
        museum_hex = p.get("museum_hex") or p.get("pass_id")
        if museum_hex:
            hex_map[museum_hex] = pass_type
    return slug_map, hex_map

def build_passes(raw_root: Path, overrides_root: Path, out_path: Path) -> dict:
    overrides = load_overrides(overrides_root)
    # Library-level pass-pickup residency policy (config/library_residency.json):
    # a blanket "museum passes restricted to <town> residents" stated on a
    # library's public page, applied below to every pass of that library whose
    # per-pass residency is still unknown.
    lr_path = raw_root.parents[1] / "config" / "library_residency.json"
    lib_residency = {}
    if lr_path.exists():
        lib_residency = {k: v for k, v in json.loads(lr_path.read_text(encoding="utf-8")).items()
                         if not k.startswith("_")}
    out_passes = []
    for platform in PLATFORMS:
        catalog_dir = raw_root / platform / "catalog"
        if not catalog_dir.exists(): continue
        for cat_f in catalog_dir.glob("*.json"):
            cat = json.loads(cat_f.read_text())
            lib = cat["library_id"]
            idx_pass_types, idx_pass_types_by_hex = _index_pass_types(raw_root, platform, lib)
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
                    # True when this library's OWN card is required to book (a
                    # same-network sibling card is rejected at card-validation).
                    # This is a CARD-OWNERSHIP fact, not residency — the card is
                    # obtainable by any MA resident. Set from the booking probe.
                    "requires_own_card": False,
                    "own_card_evidence": None,
                    "booking_access_probe": {
                        "verdict": "not_verified",
                        "source": None,
                        "evidence": None,
                        "prober_card": None,
                        "probed_date": None,
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
                pf = _pass_form_from_pass_type(
                    p.get("pass_type")
                    or idx_pass_types.get(rawslug)
                    or idx_pass_types.get(slug)
                    or idx_pass_types_by_hex.get(_detail_hex(p.get("detail_url")))
                )
                if pf:
                    row["pass_form"] = pf
                # LibCal body text is often a better pass-form signal than the
                # legacy coupon extraction, especially when old_e defaulted many
                # pickup-only passes to physical_circ.
                if platform == "libcal":
                    text_pf = infer_pass_form_from_text(p.get("benefit_text"))
                    if text_pf:
                        row["pass_form"] = text_pf
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
                # A booking probe tries to book with a SAME-NETWORK card from a
                # DIFFERENT library. Its rejection happens at card-validation and
                # means "this pass needs THIS library's OWN card" (card-ownership)
                # — NOT town residency: the card is obtainable by any MA resident.
                # So a "yes" sets requires_own_card, NOT a residency restriction.
                # A "no" (sibling card accepted) confirms the pass is network-open.
                # Neither overwrites a text-derived MA-resident requirement (a
                # separate axis the probe cannot test — the prober is a MA resident).
                probe = _read(raw_root/platform/"residency_probe"/f"{lib}__{rawslug}.json")
                if probe:
                    probe_verdict = probe.get("verdict")
                    mapped = {
                        "rejected_resident": "own_card_only",
                        "accepted": "network_open",
                        "ambiguous": "ambiguous",
                        "unknown": "ambiguous",
                        "format_error": "ambiguous",
                    }.get(probe_verdict)
                    if mapped:
                        row["booking_access_probe"] = {
                            "verdict": mapped,
                            "source": "booking_probe",
                            "evidence": probe.get("evidence"),
                            "prober_card": probe.get("prober_card"),
                            "probed_date": probe.get("probed_date"),
                        }
                # ── RESIDENCY POLICY (Pass dimension) ───────────────────────
                # residency_restriction reflects a STATED pass policy ONLY:
                #   (1) the coupon's own source_phrase_block (e.g. "X residents
                #       only"), or (2) a catalog-text residency line carried in
                #       the legacy extraction, or (3) the library-level pass-page
                #       policy from config/library_residency.json (applied below).
                # The booking probe tests CARD scope (does a sibling-network card
                # book?) — a card-OWNERSHIP fact, NOT a residency policy. It must
                # never masquerade as the pass's residency source, so it only sets
                # requires_own_card / booking_access_probe (above), never residency.
                # When no stated policy exists we leave residency 'unknown' (honest);
                # the library pass-page sweep (config) resolves it.
                text_rr = row.get("residency_restriction") or {}
                text_is_yes = text_rr.get("restricted") == "yes"
                coupon_res = residency_from_coupon(row.get("coupon"))
                if coupon_res:
                    scope, evidence = coupon_res
                    row["residency_restriction"] = {
                        "restricted": "yes", "scope": scope,
                        "source": "coupon_source_phrase", "evidence": evidence,
                    }
                elif text_is_yes:
                    pass  # keep the stated residency carried from catalog text
                else:
                    row["residency_restriction"] = {
                        "restricted": "unknown", "scope": None,
                        "source": None, "evidence": None,
                    }
                if probe and probe.get("restricted") == "yes":
                    # Sibling-network card blocked at card-validation → this pass
                    # needs THIS library's own card (card-ownership, not residency).
                    row["requires_own_card"] = True
                    row["own_card_evidence"] = probe.get("evidence")
                avail = _read(raw_root/platform/"availability"/lib/f"{rawslug}.json")
                if avail:
                    row["availability"] = {d["date"]:d["status"] for d in avail.get("days",[])}
                # Library-level pass-pickup residency: fill from the blanket
                # library policy when no stronger per-pass signal exists. Runs
                # before apply_overrides so a human override still wins.
                lr = lib_residency.get(lib)
                if lr and (row.get("residency_restriction") or {}).get("restricted") == "unknown":
                    row["residency_restriction"] = {
                        "restricted": lr.get("restricted", "yes"),
                        "scope": lr.get("scope"),
                        "source": lr.get("source") or "library_pass_policy",
                        "evidence": lr.get("evidence"),
                    }
                key = f"{lib}__{rawslug}"
                row = apply_overrides(f"pass:{key}", row, overrides)
                if is_entity_removed(f"pass:{key}", overrides):
                    continue
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
