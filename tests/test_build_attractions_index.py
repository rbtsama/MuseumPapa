"""Test extracting unique attractions across all platforms."""
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))


@pytest.fixture
def fake_raw_root(tmp_path):
    assabet = tmp_path / "raw" / "assabet" / "index"
    assabet.mkdir(parents=True)
    (assabet / "wakefield.json").write_text(json.dumps({
        "passes": [
            {"slug": "mos", "museum_name": "Museum of Science",
             "address": "1 Science Park, Boston, MA 02114",
             "website": "https://www.mos.org/visit",
             "categories": ["Science", "Family"], "status": "ok"},
            {"slug": "neaq", "museum_name": "New England Aquarium",
             "address": "1 Central Wharf, Boston, MA 02110",
             "website": "https://www.neaq.org/", "categories": ["Ocean"], "status": "ok"},
        ],
    }), encoding="utf-8")
    (assabet / "reading.json").write_text(json.dumps({
        "passes": [
            {"slug": "mos", "museum_name": "Museum of Science",
             "address": "1 Science Park, Boston, MA 02114",
             "website": "https://www.mos.org/visit",
             "categories": ["Science"], "status": "ok"},
        ],
    }), encoding="utf-8")
    return tmp_path


def test_build_attractions_index_dedupes_across_libraries(fake_raw_root):
    from scripts.build_attractions_index import build_index

    idx = build_index(fake_raw_root / "raw")

    assert set(idx.keys()) == {"mos", "neaq"}
    assert idx["mos"]["museum_name"] == "Museum of Science"
    assert idx["mos"]["website"] == "https://www.mos.org/visit"
    assert set(idx["mos"]["sources"]) == {"wakefield", "reading"}
    assert idx["neaq"]["sources"] == ["wakefield"]


def test_build_attractions_index_handles_libcal_via_platform_map(fake_raw_root):
    libcal = fake_raw_root / "raw" / "libcal" / "index"
    libcal.mkdir(parents=True)
    (libcal / "bpl.json").write_text(json.dumps({
        "passes": [
            {"libcal_pass_id": "12345", "museum_name": "Museum of Science",
             "address": "1 Science Park, Boston, MA 02114",
             "website": "https://www.mos.org/visit", "status": "ok"},
        ],
    }), encoding="utf-8")
    cfg = fake_raw_root / "config" / "platform_pass_ids"
    cfg.mkdir(parents=True)
    (cfg / "libcal.json").write_text(json.dumps({"bpl": {"12345": "mos"}}), encoding="utf-8")

    from scripts.build_attractions_index import build_index

    idx = build_index(fake_raw_root / "raw", config_root=fake_raw_root / "config")
    assert "mos" in idx
    assert "bpl" in idx["mos"]["sources"]


def test_build_attractions_index_skips_failed_passes(fake_raw_root):
    assabet = fake_raw_root / "raw" / "assabet" / "index"
    (assabet / "bad.json").write_text(json.dumps({
        "passes": [
            {"slug": "ghost", "museum_name": "Ghost", "status": "failed:parse_error"},
        ],
    }), encoding="utf-8")

    from scripts.build_attractions_index import build_index
    idx = build_index(fake_raw_root / "raw")
    assert "ghost" not in idx
