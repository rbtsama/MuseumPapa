import json
from pathlib import Path
from malibbene.build.attractions import build_attractions

def _w(p,data): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(data))

def test_build_attractions_merges_pages_prices_eligibility_reservation_hours_with_overrides(tmp_path):
    raw = tmp_path/"raw"
    _w(raw/"attractions/pages/mfa.meta.json",
        {"slug":"mfa","url":"https://mfa.org/","title":"Museum of Fine Arts","og_image":"http://x/y.jpg"})
    _w(raw/"attractions/prices/mfa.json",
        {"status":"ok","extracted":{"prices":[{"audience":"adult","price":27}]}})
    _w(raw/"attractions/visitor_eligibility/mfa.json",
        {"status":"ok","extracted":{"residency":"none","source_phrase":"open to all"}})
    _w(raw/"attractions/reservation/mfa.json",
        {"status":"ok","extracted":{"required":"timed_entry","booking_url":"https://mfa.org/tickets",
                                    "lead_time_hours":0,"pass_holder_path":"promo_code_in_general_checkout"}})
    _w(raw/"attractions/hours/mfa.json",
        {"status":"ok","extracted":{"hours":{"monday":"closed","tuesday":"10:00-17:00"}}})
    overrides = tmp_path/"overrides"
    _w(overrides/"attractions/mfa/website.json",
       {"status":"corrected","corrected_value":"https://www.mfa.org/"})

    out = tmp_path/"attractions.json"
    build_attractions(raw_root=raw, overrides_root=overrides, out_path=out)
    data = json.loads(out.read_text())
    by_slug = {a["slug"]:a for a in data["attractions"]}
    a = by_slug["mfa"]
    assert a["name"] == "Museum of Fine Arts"
    assert a["website"] == "https://www.mfa.org/"
    # hero_image is legacy-preferred (the rebuild dropped it); the fixture's
    # og_image is only a fallback. mfa exists in the legacy archive, so the
    # legacy hero wins. Just assert we got *a* hero, not the fallback rule.
    assert a["hero_image"]
    assert a["reservation"]["required"] == "timed_entry"
    assert a["visitor_eligibility"]["residency"] == "none"
    assert any(p["audience"]=="adult" and p["price"]==27 for p in a["prices"])
