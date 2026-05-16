"""Schema-lock tests for plan-6 branch model.

Asserts every pass in data/structured/passes.json carries a valid pickup_method,
that physical passes carry resolvable pickup_branches, and that
data/structured/branches.json shape is sound.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_passes_have_pickup_method():
    data = json.loads((ROOT / "data/structured/passes.json").read_text(encoding="utf-8"))
    for p in data["passes"]:
        assert p.get("pickup_method") in {"digital", "physical_at_branch"}, (
            f"{p['library_id']}/{p['attraction_slug']} missing pickup_method"
        )
        if p["pickup_method"] == "physical_at_branch":
            assert isinstance(p.get("pickup_branches"), list) and len(p["pickup_branches"]) >= 1, (
                f"{p['library_id']}/{p['attraction_slug']} physical pass needs >=1 pickup_branches"
            )


def test_branches_json_shape():
    data = json.loads((ROOT / "data/structured/branches.json").read_text(encoding="utf-8"))
    seen_ids = set()
    for b in data["branches"]:
        assert b["id"] not in seen_ids, f"duplicate branch id {b['id']}"
        seen_ids.add(b["id"])
        for k in ("id", "name", "parent_lib_id", "address", "geo"):
            assert k in b, f"branch {b.get('id')} missing {k}"
        assert b["address"].get("street")
        assert b["geo"].get("lat") and b["geo"].get("lon")


def test_pickup_branch_ids_resolve():
    branches = json.loads((ROOT / "data/structured/branches.json").read_text(encoding="utf-8"))
    valid = {b["id"] for b in branches["branches"]}
    passes = json.loads((ROOT / "data/structured/passes.json").read_text(encoding="utf-8"))
    for p in passes["passes"]:
        if p["pickup_method"] != "physical_at_branch":
            continue
        for bid in p["pickup_branches"]:
            assert bid in valid, (
                f"{p['library_id']}/{p['attraction_slug']} → unknown branch {bid}"
            )
