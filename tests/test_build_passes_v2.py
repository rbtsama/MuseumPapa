import json
from pathlib import Path
from malibbene.build.passes import build_passes

def _w(p,data): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(data))

def test_build_passes_combines_catalog_coupon_availability_and_overrides(tmp_path):
    raw = tmp_path/"raw"
    _w(raw/"assabet/catalog/wakefield.json", {"library_id":"wakefield","passes":[
        {"library_id":"wakefield","attraction_slug":"mfa","title":"MFA",
         "benefit_text":"50% off general admission","source_phrases":["50% off general admission"]}
    ]})
    _w(raw/"assabet/availability/wakefield/mfa.json",
        {"library_id":"wakefield","attraction_slug":"mfa",
         "days":[{"date":"2026-05-21","status":"available"}]})
    _w(raw/"assabet/coupons/wakefield__mfa.json",
        {"status":"ok","extracted":{
            "pass_form":"digital_email",
            "coupon":{"capacity":{"kind":"people","n":4},
                       "audience_policies":[{"audience":"Everyone","form":"percent-off","value":50}]},
            "restrictions":None}})

    out = tmp_path/"passes.json"
    build_passes(raw_root=raw, overrides_root=tmp_path/"overrides", out_path=out)
    data = json.loads(out.read_text())
    p = data["passes"][0]
    assert p["library_id"]=="wakefield" and p["attraction_slug"]=="mfa"
    assert p["pass_form"]=="digital_email"
    assert p["coupon"]["audience_policies"][0]["form"]=="percent-off"
    assert p["availability"]["2026-05-21"]=="available"

def test_build_passes_emits_rawslug_and_applies_pass_override(tmp_path):
    from malibbene.build.slug_canonical import canonical
    raw = tmp_path/"raw"
    # a suffixed catalog slug whose canonical form differs — the bug case
    _w(raw/"assabet/catalog/wakefield.json", {"library_id":"wakefield","passes":[
        {"library_id":"wakefield","attraction_slug":"mfa-promo-code","title":"MFA"}]})
    # override keyed by the RAW slug (what the build uses), correcting pass_form
    _w(tmp_path/"overrides/passes/wakefield__mfa-promo-code/pass_form.json",
       {"status":"corrected","corrected_value":"digital_email"})

    out = tmp_path/"passes.json"
    build_passes(raw_root=raw, overrides_root=tmp_path/"overrides", out_path=out)
    p = json.loads(out.read_text())["passes"][0]

    assert p["attraction_slug"] == canonical("mfa-promo-code")  # canonical join key
    assert p["attraction_rawslug"] == "mfa-promo-code"          # NEW field
    assert p["pass_form"] == "digital_email"                    # override actually applied

def test_build_passes_reads_pass_coupons_as_authoritative(tmp_path):
    # The authoritative coupon source is data/raw/pass_coupons/<lib>_<canonical>.json
    # (single underscore, top-level fields). There is NO old assabet/coupons file here —
    # the build must still emit a populated, correct coupon (was the silent-drop bug).
    raw = tmp_path/"raw"
    _w(raw/"assabet/catalog/acton.json", {"library_id":"acton","passes":[
        {"library_id":"acton","attraction_slug":"museum-of-science","title":"MoS"}]})
    _w(raw/"pass_coupons/acton_museum-of-science.json", {
        "library_id":"acton","attraction_slug":"museum-of-science","status":"ok",
        "raw":"up to 4 people at a 50% discount; children under 3 free",
        "capacity":{"kind":"people","n":4},
        "audience_policies":[
            {"audience":"Everyone","age_range":None,"count":None,"form":"percent-off","value":50},
            {"audience":"Child","age_range":{"min":None,"max":2},"count":None,"form":"free","value":None}],
        "restrictions":{"blackout_dates":[],"weekdays_only":False,"seasonal":None},
        "source_phrases":{"audience_policies[0].form":"50% discount"}})

    out = tmp_path/"passes.json"
    build_passes(raw_root=raw, overrides_root=tmp_path/"overrides", out_path=out)
    p = json.loads(out.read_text())["passes"][0]
    assert p["coupon"] is not None                                   # not silently dropped
    assert p["coupon"]["capacity"] == {"kind":"people","n":4}
    assert p["coupon"]["audience_policies"][0]["form"] == "percent-off"
    assert p["coupon"]["audience_policies"][0]["value"] == 50
    assert p["coupon"]["summary"] == "50% off"                       # generated headline
    assert "50% discount" in (p["coupon"]["source_phrase_block"] or "")  # provenance kept

def test_build_passes_pass_coupons_canonical_alias(tmp_path):
    # catalog raw slug differs from canonical; pass_coupons keyed by canonical must still match
    from malibbene.build.slug_canonical import canonical
    raw = tmp_path/"raw"
    _w(raw/"assabet/catalog/bpl.json", {"library_id":"bpl","passes":[
        {"library_id":"bpl","attraction_slug":"mfa-promo-code","title":"MFA"}]})
    canon = canonical("mfa-promo-code")
    _w(raw/f"pass_coupons/bpl_{canon}.json", {
        "library_id":"bpl","attraction_slug":canon,"status":"ok","raw":"free admission",
        "capacity":{"kind":"people","n":2},
        "audience_policies":[{"audience":"Everyone","form":"free","value":None}],
        "restrictions":{"blackout_dates":[],"weekdays_only":False,"seasonal":None}})
    out = tmp_path/"passes.json"
    build_passes(raw_root=raw, overrides_root=tmp_path/"overrides", out_path=out)
    p = json.loads(out.read_text())["passes"][0]
    assert p["coupon"] is not None and p["coupon"]["summary"] == "FREE"

def test_pass_form_derives_from_index_pass_type_over_legacy(tmp_path):
    # The catalog scrape may lack pass_type (pre-fix); the index/ snapshot carries
    # the deterministic, authoritative pass_type. It must win over a legacy old_e
    # pass_form (the LLM-guessed value that defaulted ~105 passes to physical_coupon).
    raw = tmp_path/"raw"
    _w(raw/"assabet/catalog/wakefield.json", {"library_id":"wakefield","passes":[
        {"library_id":"wakefield","attraction_slug":"pem","title":"PEM"}]})
    _w(raw/"assabet/index/wakefield.json", {"passes":[{"slug":"pem","pass_type":"digital"}]})
    _w(raw/"assabet/coupons/wakefield__pem.json",
       {"status":"ok","extracted":{"pass_form":"physical_coupon"}})
    out = tmp_path/"passes.json"
    build_passes(raw_root=raw, overrides_root=tmp_path/"overrides", out_path=out)
    p = json.loads(out.read_text())["passes"][0]
    assert p["pass_form"] == "digital_email"

def test_pass_form_uses_canonical_index_slug_when_catalog_slug_differs(tmp_path):
    # LibCal/BPL frequently drifts between catalog and index slugs:
    # "...-theatre" vs "...-theater", "...-tours", "...-physical-pass".
    # The index pass_type is still authoritative and must be recovered via the
    # canonical attraction slug.
    raw = tmp_path/"raw"
    _w(raw/"libcal/catalog/bpl.json", {"library_id":"bpl","passes":[
        {"library_id":"bpl","attraction_slug":"american-repertory-theatre","title":"ART","detail_url":"https://bpl.libcal.com/passes/5bf37dc2bee6"},
        {"library_id":"bpl","attraction_slug":"boch-center-tours","title":"Boch Center Tours","detail_url":"https://bpl.libcal.com/passes/572fd99e65a3"},
        {"library_id":"bpl","attraction_slug":"harvard-museums-of-science-and-culture-physical-pass","title":"HMSC","detail_url":"https://bpl.libcal.com/passes/92c222667367"},
    ]})
    _w(raw/"libcal/index/bpl.json", {"passes":[
        {"slug":"american-repertory-theater","pass_type":"digital","museum_hex":"5bf37dc2bee6"},
        {"slug":"boch-center","pass_type":"digital","museum_hex":"572fd99e65a3"},
        # Real BPL shape: the slug may be shortened, but the museum_hex is stable.
        {"slug":"harvard-museums","pass_type":"physical-coupon","museum_hex":"92c222667367"},
    ]})
    # Legacy extraction is wrong for all three; index canonical fallback must win.
    _w(raw/"libcal/coupons/bpl__american-repertory-theatre.json",
       {"status":"ok","extracted":{"pass_form":"physical_coupon"}})
    _w(raw/"libcal/coupons/bpl__boch-center-tours.json",
       {"status":"ok","extracted":{"pass_form":"physical_coupon"}})
    _w(raw/"libcal/coupons/bpl__harvard-museums-of-science-and-culture-physical-pass.json",
       {"status":"ok","extracted":{"pass_form":"physical_circ"}})

    out = tmp_path/"passes.json"
    build_passes(raw_root=raw, overrides_root=tmp_path/"overrides", out_path=out)
    rows = {(p["library_id"], p["attraction_slug"]): p for p in json.loads(out.read_text())["passes"]}

    assert rows[("bpl", "american-repertory-theater")]["pass_form"] == "digital_email"
    assert rows[("bpl", "boch-center")]["pass_form"] == "digital_email"
    assert rows[("bpl", "harvard-museums-of-science-and-culture")]["pass_form"] == "physical_coupon"

def test_libcal_catalog_text_can_override_wrong_legacy_pass_form(tmp_path):
    raw = tmp_path/"raw"
    _w(raw/"libcal/catalog/cambridge.json", {"library_id":"cambridge","passes":[
        {"library_id":"cambridge","attraction_slug":"harvard-museums-of-science-culture",
         "title":"HMSC","benefit_text":"Physical passes must be picked up from one of the library locations listed in the dropdown menu below.",
         "detail_url":"https://cambridgepl.libcal.com/passes/harvard-museums-of-science-and-culture"},
        {"library_id":"cambridge","attraction_slug":"trustees-go-pass",
         "title":"Trustees","benefit_text":"SEASONAL PASS. Physical passes must be picked up from one of the library locations listed in the dropdown menu below.",
         "detail_url":"https://cambridgepl.libcal.com/passes/trustees-go-pass"},
        {"library_id":"cambridge","attraction_slug":"zoo-new-england",
         "title":"Zoo","benefit_text":"Physical passes must be picked up from one of the library locations listed in the dropdown menu below.",
         "detail_url":"https://cambridgepl.libcal.com/passes/zoo-new-england"},
    ]})
    _w(raw/"libcal/coupons/cambridge__harvard-museums-of-science-culture.json",
       {"status":"ok","extracted":{"pass_form":"physical_circ"}})
    _w(raw/"libcal/coupons/cambridge__trustees-go-pass.json",
       {"status":"ok","extracted":{"pass_form":"physical_circ"}})
    _w(raw/"libcal/coupons/cambridge__zoo-new-england.json",
       {"status":"ok","extracted":{"pass_form":"physical_circ"}})

    out = tmp_path/"passes.json"
    build_passes(raw_root=raw, overrides_root=tmp_path/"overrides", out_path=out)
    rows = {(p["library_id"], p["attraction_slug"]): p for p in json.loads(out.read_text())["passes"]}

    assert rows[("cambridge", "harvard-museums-of-science-and-culture")]["pass_form"] == "physical_coupon"
    assert rows[("cambridge", "trustees-of-reservations")]["pass_form"] == "physical_coupon"
    assert rows[("cambridge", "zoo-new-england")]["pass_form"] == "physical_coupon"

def test_pass_form_from_catalog_pass_type(tmp_path):
    # After the scraper fix, catalog records carry pass_type directly.
    raw = tmp_path/"raw"
    _w(raw/"assabet/catalog/wakefield.json", {"library_id":"wakefield","passes":[
        {"library_id":"wakefield","attraction_slug":"gables","pass_type":"physical-circ"}]})
    out = tmp_path/"passes.json"
    build_passes(raw_root=raw, overrides_root=tmp_path/"overrides", out_path=out)
    p = json.loads(out.read_text())["passes"][0]
    assert p["pass_form"] == "physical_circ"

def test_pass_coupons_restrictions_win_over_legacy(tmp_path):
    # crec (data/raw/pass_coupons) is authoritative for the coupon; its restrictions
    # must also win over the stale legacy old_e.restrictions (B2 precedence fix).
    raw = tmp_path/"raw"
    _w(raw/"assabet/catalog/wakefield.json", {"library_id":"wakefield","passes":[
        {"library_id":"wakefield","attraction_slug":"mfa"}]})
    _w(raw/"assabet/coupons/wakefield__mfa.json", {"status":"ok","extracted":{
        "restrictions": {"weekdays_only": True, "blackout": [], "seasonal": None}}})
    _w(raw/"pass_coupons/wakefield_mfa.json", {
        "library_id":"wakefield","attraction_slug":"mfa","status":"ok","raw":"x",
        "capacity":{"kind":"people","n":2},
        "audience_policies":[{"audience":"Everyone","form":"free"}],
        "restrictions":{"blackout_dates":["2026-12-25"],"weekdays_only":False,"seasonal":None}})
    out = tmp_path/"passes.json"
    build_passes(raw_root=raw, overrides_root=tmp_path/"overrides", out_path=out)
    p = json.loads(out.read_text())["passes"][0]
    assert p["restrictions"]["weekdays_only"] is False                 # crec, not legacy True
    assert p["restrictions"]["blackout"] == [{"month": 12, "day": 25}]  # crec blackout present

def test_booking_probe_rejection_is_own_card_not_residency(tmp_path):
    # A probe rejection (same-network sibling card blocked at card-validation)
    # means "needs THIS library's own card" — card-ownership, NOT town residency.
    # It must set requires_own_card and NOT a town residency_restriction.
    raw = tmp_path/"raw"
    _w(raw/"assabet/catalog/wakefield.json", {"library_id":"wakefield","passes":[
        {"library_id":"wakefield","attraction_slug":"mfa","title":"MFA"}]})
    _w(raw/"assabet/residency_probe/wakefield__mfa.json", {
        "library_id":"wakefield","attraction_slug":"mfa","prober_card":"reading",
        "verdict":"rejected_resident","restricted":"yes","scope":"town",
        "evidence":"non-resident reading card (same NOBLE network) blocked at card-validation"})
    out = tmp_path/"passes.json"
    build_passes(raw_root=raw, overrides_root=tmp_path/"overrides", out_path=out)
    p = json.loads(out.read_text())["passes"][0]
    assert p["requires_own_card"] is True
    assert p["residency_restriction"]["restricted"] == "no"   # NOT yes/town
    assert p["residency_restriction"]["scope"] is None
    assert p["booking_access_probe"] == {
        "verdict": "own_card_only",
        "source": "booking_probe",
        "evidence": "non-resident reading card (same NOBLE network) blocked at card-validation",
        "prober_card": "reading",
        "probed_date": None,
    }

def test_booking_probe_acceptance_is_network_open(tmp_path):
    # A probe acceptance (sibling card accepted) -> network-open, own card not required.
    raw = tmp_path/"raw"
    _w(raw/"assabet/catalog/acton.json", {"library_id":"acton","passes":[
        {"library_id":"acton","attraction_slug":"mfa","title":"MFA"}]})
    _w(raw/"assabet/residency_probe/acton__mfa.json", {
        "library_id":"acton","attraction_slug":"mfa","prober_card":"somerville",
        "verdict":"accepted","restricted":"no","scope":None,
        "evidence":"non-resident somerville card (same Minuteman network) accepted at card-validation"})
    out = tmp_path/"passes.json"
    build_passes(raw_root=raw, overrides_root=tmp_path/"overrides", out_path=out)
    p = json.loads(out.read_text())["passes"][0]
    assert p["requires_own_card"] is False
    assert p["residency_restriction"]["restricted"] == "no"
    assert p["booking_access_probe"] == {
        "verdict": "network_open",
        "source": "booking_probe",
        "evidence": "non-resident somerville card (same Minuteman network) accepted at card-validation",
        "prober_card": "somerville",
        "probed_date": None,
    }


def test_pass_without_probe_stays_not_verified(tmp_path):
    raw = tmp_path/"raw"
    _w(raw/"assabet/catalog/wakefield.json", {"library_id":"wakefield","passes":[
        {"library_id":"wakefield","attraction_slug":"mfa","title":"MFA"}]})
    out = tmp_path/"passes.json"
    build_passes(raw_root=raw, overrides_root=tmp_path/"overrides", out_path=out)
    p = json.loads(out.read_text())["passes"][0]
    assert p["booking_access_probe"]["verdict"] == "not_verified"
    assert p["booking_access_probe"]["source"] is None


def test_ambiguous_booking_probe_is_preserved_without_forcing_own_card(tmp_path):
    raw = tmp_path/"raw"
    _w(raw/"assabet/catalog/wakefield.json", {"library_id":"wakefield","passes":[
        {"library_id":"wakefield","attraction_slug":"mfa","title":"MFA"}]})
    _w(raw/"assabet/residency_probe/wakefield__mfa.json", {
        "library_id":"wakefield","attraction_slug":"mfa","prober_card":"reading",
        "probed_date":None,"verdict":"ambiguous","restricted":"unknown","scope":None,
        "evidence":"inconclusive booking probe via reading card; attempts=format_error,unknown"})
    out = tmp_path/"passes.json"
    build_passes(raw_root=raw, overrides_root=tmp_path/"overrides", out_path=out)
    p = json.loads(out.read_text())["passes"][0]
    assert p["requires_own_card"] is False
    assert p["booking_access_probe"] == {
        "verdict": "ambiguous",
        "source": "booking_probe",
        "evidence": "inconclusive booking probe via reading card; attempts=format_error,unknown",
        "prober_card": "reading",
        "probed_date": None,
    }

def test_coupon_coverage_gaps_detects_silent_drop(tmp_path):
    from malibbene.build.coupons import coupon_coverage_gaps
    (tmp_path/"pass_coupons").mkdir(parents=True)
    (tmp_path/"pass_coupons/acton_mfa.json").write_text(
        json.dumps({"status":"ok","audience_policies":[{"form":"free"}]}))
    # empty coupon but authoritative raw exists -> flagged as a silent drop
    dropped = [{"library_id":"acton","attraction_slug":"mfa","attraction_rawslug":"mfa","coupon":None}]
    assert coupon_coverage_gaps(dropped, tmp_path) == [("acton","mfa")]
    # populated coupon -> no gap; missing raw file -> no gap
    ok = [{"library_id":"acton","attraction_slug":"mfa","attraction_rawslug":"mfa","coupon":{"x":1}},
          {"library_id":"x","attraction_slug":"y","attraction_rawslug":"y","coupon":None}]
    assert coupon_coverage_gaps(ok, tmp_path) == []
