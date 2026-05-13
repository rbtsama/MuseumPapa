"""Unit test for ``scripts/snapshot_diff.diff_one_file``."""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import snapshot_diff  # noqa: E402


def _write(tmp: Path, name: str, passes: list[dict]) -> Path:
    p = tmp / name
    p.write_text(json.dumps({"passes": passes}), encoding="utf-8")
    return p


def test_added_and_removed_slugs(tmp_path):
    today = _write(tmp_path, "today.json", [{"slug": "a", "pass_type": "digital", "label": "Free"}])
    prior = _write(tmp_path, "prior.json", [{"slug": "b", "pass_type": "digital", "label": "Free"}])
    d = snapshot_diff.diff_one_file(today, prior)
    assert d["added"] == ["a"]
    assert d["removed"] == ["b"]
    assert d["field_changes"] == []


def test_field_change_pass_type(tmp_path):
    today = _write(tmp_path, "t.json", [{"slug": "a", "pass_type": "digital", "label": "Free", "benefits_text": "x"}])
    prior = _write(tmp_path, "p.json", [{"slug": "a", "pass_type": "physical-circ", "label": "Free", "benefits_text": "x"}])
    d = snapshot_diff.diff_one_file(today, prior)
    assert d["added"] == [] and d["removed"] == []
    pt = [fc for fc in d["field_changes"] if fc["field"] == "pass_type"]
    assert pt == [{"slug": "a", "field": "pass_type", "from": "physical-circ", "to": "digital"}]


def test_missing_today_means_file_removed(tmp_path):
    prior = _write(tmp_path, "p.json", [{"slug": "a"}])
    d = snapshot_diff.diff_one_file(None, prior)
    assert d["prior_total"] == 1
    assert d["today_total"] == 0
    assert d["removed"] == ["a"]


def test_benefits_text_whitespace_ignored(tmp_path):
    """Whitespace/trailing punctuation diffs alone should NOT flag a change."""
    today = _write(tmp_path, "t.json", [{"slug": "a", "benefits_text": "Pass admits 4.  "}])
    prior = _write(tmp_path, "p.json", [{"slug": "a", "benefits_text": "Pass\nadmits\n4"}])
    d = snapshot_diff.diff_one_file(today, prior)
    assert d["field_changes"] == []
