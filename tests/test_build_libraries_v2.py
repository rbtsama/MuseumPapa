import json
from pathlib import Path
from malibbene.build.libraries import build_libraries

def _w(p,data): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(data))

def test_build_merges_seed_policy_and_overrides(tmp_path):
    seed = [{"id":"wakefield","name":"L Beebe","town":"Wakefield","network":"NOBLE",
             "platform":"assabet","card_page":"http://x","domain":"wakefieldlibrary.org"}]
    seed_path = tmp_path/"library_seeds.json"; seed_path.write_text(json.dumps(seed))

    raw = tmp_path/"raw"
    _w(raw/"assabet/policies/wakefield.json", {
        "card_page": {"card_eligibility":"unknown"},
        "pass_page": {"pass_pickup":"unknown"},
    })
    overrides = tmp_path/"overrides"
    _w(overrides/"libraries/wakefield/card_eligibility.json",
       {"status":"corrected","corrected_value":"ma_resident","note":"verified"})

    out = tmp_path/"libraries.json"
    build_libraries(seed_path=seed_path, raw_root=raw, overrides_root=overrides, out_path=out)
    data = json.loads(out.read_text())
    libs = data["libraries"]
    assert libs[0]["id"] == "wakefield"
    assert libs[0]["card_eligibility"] == "ma_resident"
    assert libs[0]["pass_pickup_default"] == "unknown"
    assert libs[0]["consortium_label"] == "NOBLE"
    assert libs[0]["card_issuance_group"] == "NOBLE"
    assert libs[0]["card_issuance_groups"] == ["NOBLE"]
    assert libs[0]["card_auth_groups"] == ["NOBLE"]

def test_build_libraries_keeps_explicit_card_access_groups(tmp_path):
    seed = [{
        "id":"bpl","name":"Boston Public Library","town":"Boston","network":"BPL",
        "consortium_label":"BPL","card_auth_groups":["BPL", "MBLN"],
        "platform":"libcal","card_page":"http://x","domain":"bpl.libcal.com"
    }]
    seed_path = tmp_path/"library_seeds.json"; seed_path.write_text(json.dumps(seed))
    raw = tmp_path/"raw"
    overrides = tmp_path/"overrides"

    out = tmp_path/"libraries.json"
    build_libraries(seed_path=seed_path, raw_root=raw, overrides_root=overrides, out_path=out)
    lib = json.loads(out.read_text())["libraries"][0]

    assert lib["consortium_label"] == "BPL"
    assert lib["card_issuance_group"] == "BPL"
    assert lib["card_issuance_groups"] == ["BPL"]
    assert lib["card_auth_groups"] == ["BPL", "MBLN"]
