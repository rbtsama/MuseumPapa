import json
import hashlib
from pathlib import Path
import pytest
from malibbene.build.validate import validate_build, build_source_url_fetcher


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


def test_check_build_consistency_raises_on_skew(tmp_path):
    from malibbene.build.validate import check_build_consistency
    stamps = {"libraries": "2026-05-22T18:00:00+00:00", "attractions": "2026-05-22T18:00:05+00:00",
              "branches": "2026-05-22T18:00:02+00:00", "passes": "2026-05-25T16:00:00+00:00"}  # 3-day skew
    for f, ts in stamps.items():
        (tmp_path/f"{f}.json").write_text(json.dumps({"_meta": {"built_at": ts}}))
    with pytest.raises(ValueError, match="built"):
        check_build_consistency(tmp_path)


def test_check_build_consistency_passes_when_built_together(tmp_path):
    from malibbene.build.validate import check_build_consistency
    stamps = {"libraries": "2026-05-22T18:00:00+00:00", "attractions": "2026-05-22T18:00:05+00:00",
              "branches": "2026-05-22T18:00:02+00:00", "passes": "2026-05-22T18:00:11+00:00"}
    for f, ts in stamps.items():
        (tmp_path/f"{f}.json").write_text(json.dumps({"_meta": {"built_at": ts}}))
    check_build_consistency(tmp_path)  # within one run -> no raise


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

def test_validate_reports_libcal_pass_form_conflicts_from_catalog_text(tmp_path):
    raw = tmp_path/"raw"
    (raw/"libcal"/"catalog").mkdir(parents=True)
    (raw/"libcal"/"catalog"/"bpl.json").write_text(json.dumps({
        "library_id":"bpl",
        "passes":[
            {"attraction_slug":"american-repertory-theatre",
             "benefit_text":"Digital (downloadable via email) passes are available."},
            {"attraction_slug":"harvard-museums-of-science-and-culture-physical-pass",
             "benefit_text":"This pass must be picked up at the branch. This pass does not need to be returned."},
        ],
    }))
    lp, ap, pp = _write(tmp_path,
        [{"id":"bpl"}],
        [{"slug":"american-repertory-theater"}, {"slug":"harvard-museums-of-science-and-culture"}],
        [
            {"library_id":"bpl","attraction_slug":"american-repertory-theater","pass_form":"physical_coupon","coupon":None},
            {"library_id":"bpl","attraction_slug":"harvard-museums-of-science-and-culture","pass_form":"physical_circ","coupon":None},
        ])
    report = validate_build(libraries=lp, attractions=ap, passes_file=pp, raw_root=raw)
    assert report["passes"]["pass_form_catalog_conflict_count"] == 2
    sample = report["passes"]["pass_form_catalog_conflict_samples"]
    assert {"library_id":"bpl","attraction_slug":"american-repertory-theater","expected":"digital_email","actual":"physical_coupon"} in sample
    assert {"library_id":"bpl","attraction_slug":"harvard-museums-of-science-and-culture","expected":"physical_coupon","actual":"physical_circ"} in sample

def test_validate_reports_dead_source_urls_via_injected_fetcher(tmp_path):
    lp, ap, pp = _write(tmp_path,
        [{"id":"bpl"}],
        [{"slug":"x"}, {"slug":"y"}],
        [
            {"library_id":"bpl","attraction_slug":"x","coupon":None,"source_url":"https://ok.example/x"},
            {"library_id":"bpl","attraction_slug":"y","coupon":None,"source_url":"https://dead.example/y"},
        ])
    def fake_fetch(url: str):
        return 404 if "dead.example" in url else 200
    report = validate_build(libraries=lp, attractions=ap, passes_file=pp, source_url_fetcher=fake_fetch)
    assert report["passes"]["dead_source_url_count"] == 1
    assert report["passes"]["dead_source_url_samples"] == [{
        "library_id":"bpl",
        "attraction_slug":"y",
        "status":404,
        "source_url":"https://dead.example/y",
    }]


def test_validate_reports_booking_probe_own_card_conflicts(tmp_path):
    lp, ap, pp = _write(tmp_path,
        [{"id":"belmont"}],
        [{"slug":"x"}, {"slug":"y"}],
        [
            {
                "library_id":"belmont",
                "attraction_slug":"x",
                "coupon":None,
                "requires_own_card":False,
                "own_card_evidence":"non-resident somerville card (same Minuteman network) blocked at card-validation",
                "residency_restriction":{"restricted":"no","source":"booking_probe_card_ownership","evidence":"same evidence"},
            },
            {
                "library_id":"belmont",
                "attraction_slug":"y",
                "coupon":None,
                "requires_own_card":True,
                "residency_restriction":{"restricted":"no","source":"booking_probe","evidence":"booking probe: same-network card accepted"},
            },
        ])
    report = validate_build(libraries=lp, attractions=ap, passes_file=pp)
    assert report["passes"]["booking_probe_own_card_conflict_count"] == 2
    assert report["passes"]["booking_probe_own_card_conflict_samples"] == [
        {
            "library_id":"belmont",
            "attraction_slug":"x",
            "issue":"probe_blocked_but_requires_own_card_false",
        },
        {
            "library_id":"belmont",
            "attraction_slug":"y",
            "issue":"probe_accepted_but_requires_own_card_true",
        },
    ]


def test_validate_reports_booking_probe_residency_miswire(tmp_path):
    lp, ap, pp = _write(tmp_path,
        [{"id":"belmont"}],
        [{"slug":"x"}],
        [{
            "library_id":"belmont",
            "attraction_slug":"x",
            "coupon":None,
            "requires_own_card":True,
            "residency_restriction":{"restricted":"yes","source":"booking_probe_card_ownership","evidence":"blocked at card-validation"},
        }])
    report = validate_build(libraries=lp, attractions=ap, passes_file=pp)
    assert report["passes"]["booking_probe_own_card_conflict_count"] == 1
    assert report["passes"]["booking_probe_own_card_conflict_samples"] == [{
        "library_id":"belmont",
        "attraction_slug":"x",
        "issue":"booking_probe_card_ownership_must_not_set_residency_block",
        "actual_restricted":"yes",
    }]


def test_source_url_fetcher_uses_fresh_cache(tmp_path):
    cache_path = tmp_path/"source_url_status.json"
    url = "https://cached.example/x"
    cache_path.write_text(json.dumps({
        hashlib.sha1(url.encode("utf-8")).hexdigest(): {
            "url": url,
            "status": 404,
            "checked_at": 1000,
        }
    }))
    calls = []

    def fake_fetch(url: str):
        calls.append(url)
        return 200

    fetcher = build_source_url_fetcher(
        fetcher=fake_fetch,
        cache_path=cache_path,
        ttl_seconds=3600,
        now=1200,
    )
    assert fetcher(url) == 404
    assert calls == []


def test_source_url_fetcher_refreshes_expired_cache(tmp_path):
    cache_path = tmp_path/"source_url_status.json"
    url = "https://stale.example/x"
    cache_path.write_text(json.dumps({
        hashlib.sha1(url.encode("utf-8")).hexdigest(): {
            "url": url,
            "status": 404,
            "checked_at": 1000,
        }
    }))
    calls = []

    def fake_fetch(url: str):
        calls.append(url)
        return 200

    fetcher = build_source_url_fetcher(
        fetcher=fake_fetch,
        cache_path=cache_path,
        ttl_seconds=100,
        now=1200,
    )
    assert fetcher(url) == 200
    assert calls == [url]
    cached = json.loads(cache_path.read_text(encoding="utf-8"))
    assert next(iter(cached.values()))["status"] == 200


def test_source_url_fetcher_does_not_cache_transient_none(tmp_path):
    cache_path = tmp_path/"source_url_status.json"
    calls = []

    def fake_fetch(url: str):
        calls.append(url)
        return None

    fetcher = build_source_url_fetcher(
        fetcher=fake_fetch,
        cache_path=cache_path,
        ttl_seconds=3600,
        now=1200,
    )
    assert fetcher("https://transient.example/x") is None
    assert calls == ["https://transient.example/x"]
    assert not cache_path.exists()
