import json
from pathlib import Path
from malibbene.common.audit_overrides import load_overrides, apply_overrides, merge_override, remove_override

def _write(p: Path, data: dict):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data))

def test_load_overrides_indexes_by_target(tmp_path):
    _write(tmp_path / "libraries/wakefield/card_eligibility.json",
           {"status":"corrected","corrected_value":"ma_resident","note":"re-checked"})
    _write(tmp_path / "passes/wakefield__mfa/eligibility_override.json",
           {"status":"corrected","corrected_value":{"residency":"town_resident","reason":"x"}})

    by_target = load_overrides(tmp_path)
    assert "library:wakefield:card_eligibility" in by_target
    assert by_target["library:wakefield:card_eligibility"]["corrected_value"] == "ma_resident"
    assert "pass:wakefield__mfa:eligibility_override" in by_target

def test_apply_overrides_replaces_field_value():
    raw = {"id":"wakefield","card_eligibility":"unknown","town":"Wakefield"}
    overrides = {"library:wakefield:card_eligibility":
                 {"status":"corrected","corrected_value":"ma_resident"}}
    result = apply_overrides("library:wakefield", raw, overrides)
    assert result["card_eligibility"] == "ma_resident"
    assert result["town"] == "Wakefield"

def test_apply_ignores_noted_status_keeps_raw():
    raw = {"id":"x","field":"a"}
    overrides = {"library:x:field": {"status":"noted","note":"weird but ok"}}
    result = apply_overrides("library:x", raw, overrides)
    assert result["field"] == "a"

def test_load_overrides_reads_consolidated_file(tmp_path):
    # legacy dir-tree record
    _write(tmp_path / "libraries/wakefield/card_eligibility.json",
           {"status":"corrected","corrected_value":"ma_resident"})
    # consolidated file the panel writes
    (tmp_path / "audit_overrides.json").write_text(json.dumps({
        "attraction:mfa:visitor_eligibility": {
            "target":"attraction:mfa:visitor_eligibility","kind":"attraction",
            "id":"mfa","field":"visitor_eligibility","status":"corrected",
            "corrected_value":{"residency":"ma_resident"},
            "correction_kind":"value_wrong","root_cause":"extraction_error",
            "note":"","audited_at":"2026-05-25T00:00:00Z"},
    }))
    by_target = load_overrides(tmp_path)
    assert "library:wakefield:card_eligibility" in by_target          # dir tree still works
    assert "attraction:mfa:visitor_eligibility" in by_target          # consolidated loaded
    assert by_target["attraction:mfa:visitor_eligibility"]["corrected_value"] == {"residency":"ma_resident"}

def test_consolidated_file_wins_over_dir_tree(tmp_path):
    _write(tmp_path / "libraries/wakefield/card_eligibility.json",
           {"status":"corrected","corrected_value":"town_resident"})
    (tmp_path / "audit_overrides.json").write_text(json.dumps({
        "library:wakefield:card_eligibility": {
            "status":"corrected","corrected_value":"ma_resident"},
    }))
    by_target = load_overrides(tmp_path)
    assert by_target["library:wakefield:card_eligibility"]["corrected_value"] == "ma_resident"

def test_merge_override_upserts_by_target():
    store = {}
    rec = {"target":"library:x:card_eligibility","status":"corrected","corrected_value":"none"}
    merge_override(store, rec)
    assert store["library:x:card_eligibility"]["corrected_value"] == "none"
    # second write to same target replaces
    merge_override(store, {"target":"library:x:card_eligibility","status":"verified_ok"})
    assert store["library:x:card_eligibility"]["status"] == "verified_ok"

def test_merge_override_requires_target():
    import pytest
    with pytest.raises(ValueError):
        merge_override({}, {"status":"corrected"})

def test_remove_override_deletes_target():
    store = {"library:x:f": {"target":"library:x:f","status":"noted"}}
    remove_override(store, "library:x:f")
    assert "library:x:f" not in store
    remove_override(store, "missing:y:z")  # no error on missing
