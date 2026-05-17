"""Schema lock for Pass.coupon — keeps build output stable across refactors."""
import json
import pathlib


def test_coupon_raw_extraction_schema_lock():
    """Each pass_coupons/*.json file must conform to the locked schema."""
    raw_dir = pathlib.Path(__file__).resolve().parents[1] / "data" / "raw" / "pass_coupons"
    files = sorted(str(p) for p in raw_dir.glob("*.json"))
    if not files:
        # Plan-9 not yet executed past Task 2; skip when raw dir empty.
        import pytest
        pytest.skip("data/raw/pass_coupons/ is empty; Task 2 must run first")

    required_top = {"library_id", "attraction_slug", "status", "raw",
                    "capacity", "audience_policies", "source_phrases"}
    required_capacity = {"kind", "n"}
    valid_kinds = {"people", "vehicle", "ticket", "unspecified"}
    valid_audiences = {"Everyone", "Adult", "Child", "Youth", "Senior",
                       "Vehicle", "Single ticket"}
    valid_forms = {"free", "percent-off", "dollar-off", "per-person-price", "discount"}

    for f in files:
        with open(f, encoding='utf-8') as fh:
            d = json.load(fh)
        missing = required_top - set(d.keys())
        assert not missing, f"{f}: missing keys {missing}"
        if d["status"] != "ok":
            continue
        cap_missing = required_capacity - set(d["capacity"].keys())
        assert not cap_missing, f"{f}: capacity missing {cap_missing}"
        assert d["capacity"]["kind"] in valid_kinds, f"{f}: bad capacity.kind"
        assert isinstance(d["audience_policies"], list)
        assert len(d["audience_policies"]) >= 1, f"{f}: empty audience_policies"
        for i, ap in enumerate(d["audience_policies"]):
            assert ap["audience"] in valid_audiences, f"{f}: ap[{i}].audience"
            assert ap["form"] in valid_forms, f"{f}: ap[{i}].form"
            if ap.get("age_range") is not None:
                assert "min" in ap["age_range"] and "max" in ap["age_range"]
