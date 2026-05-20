import json
from pathlib import Path
from malibbene.build.validate import validate_build

def test_validate_reports_unknown_percentages(tmp_path):
    libs = tmp_path/"libraries.json"; libs.write_text(json.dumps({"libraries":[
        {"id":"a","card_eligibility":"unknown","pass_pickup_default":"unknown"},
        {"id":"b","card_eligibility":"ma_resident","pass_pickup_default":"unknown"},
    ]}))
    attrs = tmp_path/"attractions.json"; attrs.write_text(json.dumps({"attractions":[
        {"slug":"x","visitor_eligibility":None},
        {"slug":"y","visitor_eligibility":{"residency":"none"}},
    ]}))
    passes = tmp_path/"passes.json"; passes.write_text(json.dumps({"passes":[
        {"library_id":"a","attraction_slug":"x","coupon":None},
        {"library_id":"b","attraction_slug":"y","coupon":{"audience_policies":[]}},
    ]}))
    report = validate_build(libraries=libs, attractions=attrs, passes_file=passes)
    assert report["libraries"]["card_eligibility_unknown_pct"] == 50.0
    assert report["attractions"]["visitor_eligibility_missing_pct"] == 50.0
    assert report["passes"]["coupon_missing_pct"] == 50.0
