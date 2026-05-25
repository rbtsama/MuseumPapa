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
