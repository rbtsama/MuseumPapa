import json
from pathlib import Path
import pytest
from malibbene.build.validate import validate_build


def _write(tmp_path, libs, attrs, passes):
    lp = tmp_path/"libraries.json"; lp.write_text(json.dumps({"libraries": libs}))
    ap = tmp_path/"attractions.json"; ap.write_text(json.dumps({"attractions": attrs}))
    pp = tmp_path/"passes.json"; pp.write_text(json.dumps({"passes": passes}))
    return lp, ap, pp


def test_validate_raises_on_orphan_attraction(tmp_path):
    lp, ap, pp = _write(tmp_path,
        [{"id": "a"}],
        [{"slug": "x"}],
        [{"library_id": "a", "attraction_slug": "ghost", "coupon": None}])
    with pytest.raises(ValueError, match="attraction"):
        validate_build(libraries=lp, attractions=ap, passes_file=pp)


def test_validate_raises_on_orphan_library(tmp_path):
    lp, ap, pp = _write(tmp_path,
        [{"id": "a"}],
        [{"slug": "x"}],
        [{"library_id": "ghost", "attraction_slug": "x", "coupon": None}])
    with pytest.raises(ValueError, match="library"):
        validate_build(libraries=lp, attractions=ap, passes_file=pp)


def test_validate_raises_on_duplicate_pair(tmp_path):
    lp, ap, pp = _write(tmp_path,
        [{"id": "a"}],
        [{"slug": "x"}],
        [{"library_id": "a", "attraction_slug": "x", "coupon": None},
         {"library_id": "a", "attraction_slug": "x", "coupon": None}])
    with pytest.raises(ValueError, match="duplicate"):
        validate_build(libraries=lp, attractions=ap, passes_file=pp)


def test_validate_reports_data_quality_metrics(tmp_path):
    lp, ap, pp = _write(tmp_path,
        [{"id": "a"}],
        [{"slug": "x", "categories": []}, {"slug": "y", "categories": ["Art"]}],
        [{"library_id": "a", "attraction_slug": "x", "coupon": {
            "audience_policies": [{"audience": "Child"}, {"audience": "Child"}]}}])
    report = validate_build(libraries=lp, attractions=ap, passes_file=pp)
    assert report["attractions"]["empty_categories_count"] == 1
    assert report["passes"]["duplicate_audience_count"] == 1

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
