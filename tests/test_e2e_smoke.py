"""End-to-end smoke tests after full rebuild.

Tolerances reflect actual 2026-05-20 partial scrape:
  - 19/59 libraries scraped (rate limiting), but seeds give us all 59
  - 48 attractions with LLM-extracted visitor_eligibility + reservation
  - 395 passes from 23 catalog files
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_libraries_has_at_least_50_entries():
    d = json.loads((ROOT / "data/structured/libraries.json").read_text(encoding="utf-8"))
    assert d["_meta"]["n_libraries"] >= 50


def test_attractions_has_visitor_eligibility_field_populated():
    d = json.loads((ROOT / "data/structured/attractions.json").read_text(encoding="utf-8"))
    with_ve = [a for a in d["attractions"] if a.get("visitor_eligibility")]
    assert len(with_ve) / len(d["attractions"]) >= 0.5  # >= 50%


def test_blackout_uses_relative_dates():
    d = json.loads((ROOT / "data/structured/passes.json").read_text(encoding="utf-8"))
    for p in d["passes"]:
        for b in (p.get("restrictions") or {}).get("blackout", []):
            assert "year" not in b
            assert "month" in b and "day" in b


def test_bpl_has_branches():
    d = json.loads((ROOT / "data/structured/branches.json").read_text(encoding="utf-8"))
    bpl_branches = [b for b in d["branches"] if b["library_id"] == "bpl"]
    assert len(bpl_branches) >= 15


def test_passes_have_required_fields():
    d = json.loads((ROOT / "data/structured/passes.json").read_text(encoding="utf-8"))
    assert len(d["passes"]) > 0
    for p in d["passes"][:20]:
        assert "library_id" in p
        assert "attraction_slug" in p
        assert "pass_form" in p
