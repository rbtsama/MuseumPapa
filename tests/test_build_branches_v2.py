import json
from pathlib import Path
from malibbene.build.branches import build_branches

def test_build_branches_includes_all_libcal_libraries(tmp_path):
    raw = tmp_path/"raw"
    p = raw/"libcal/branches/bpl.json"; p.parent.mkdir(parents=True)
    p.write_text(json.dumps({"library_id":"bpl",
        "branches":[{"id":"bpl-brighton","library_id":"bpl","name":"Brighton"}]}))
    out = tmp_path/"branches.json"
    build_branches(raw_root=raw, overrides_root=tmp_path/"overrides", out_path=out)
    data = json.loads(out.read_text())
    assert len(data["branches"]) == 1
    assert data["branches"][0]["id"] == "bpl-brighton"
