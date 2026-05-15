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


def test_libcal_bpl_uses_inverted_pass_id_map(tmp_path):
    """BPL libcal: raw pass.pass_id (12-hex) reverse-maps via bpl.json."""
    libcal = tmp_path / "raw" / "libcal" / "index"
    libcal.mkdir(parents=True)
    (libcal / "bpl.json").write_text(json.dumps({
        "passes": [
            {"pass_id": "abc123", "slug": "some-libcal-page-slug",
             "museum_name": "Museum of Science",
             "website": "https://www.mos.org/visit", "status": "ok"},
        ],
    }), encoding="utf-8")
    cfg = tmp_path / "config" / "platform_pass_ids"
    cfg.mkdir(parents=True)
    (cfg / "bpl.json").write_text(json.dumps({
        "passes": {"mos": "abc123"}
    }), encoding="utf-8")

    from scripts.build_attractions_index import build_index
    idx = build_index(tmp_path / "raw", config_root=tmp_path / "config")
    assert "mos" in idx
    assert "bpl" in idx["mos"]["sources"]


def test_libcal_non_bpl_uses_nested_slug_map(tmp_path):
    """Non-BPL libcal: raw pass.slug (libcal-side) -> canonical via libcal.json[lib_id]."""
    libcal = tmp_path / "raw" / "libcal" / "index"
    libcal.mkdir(parents=True)
    (libcal / "cambridge.json").write_text(json.dumps({
        "passes": [
            {"pass_id": "ignored", "slug": "libcal-side-slug",
             "museum_name": "Some Attraction", "status": "ok"},
        ],
    }), encoding="utf-8")
    cfg = tmp_path / "config" / "platform_pass_ids"
    cfg.mkdir(parents=True)
    (cfg / "libcal.json").write_text(json.dumps({
        "libraries": {
            "cambridge": {
                "domain": "cambridgepl.libcal.com",
                "passes": {"libcal-side-slug": "canonical-slug"},
            }
        }
    }), encoding="utf-8")

    from scripts.build_attractions_index import build_index
    idx = build_index(tmp_path / "raw", config_root=tmp_path / "config")
    assert "canonical-slug" in idx
    assert "cambridge" in idx["canonical-slug"]["sources"]


def test_museumkey_uses_name_to_benefit(tmp_path):
    """museumkey: raw.slug NOT in canonical_set -> fall back to name_to_benefit[museum_name.lower()]."""
    mk = tmp_path / "raw" / "museumkey" / "index"
    mk.mkdir(parents=True)
    (mk / "cohasset.json").write_text(json.dumps({
        "passes": [
            {"slug": "something-else", "museum_name": "Museum of Science",
             "status": "ok"},
        ],
    }), encoding="utf-8")
    cfg = tmp_path / "config" / "platform_pass_ids"
    cfg.mkdir(parents=True)
    (cfg / "museumkey.json").write_text(json.dumps({
        "name_to_benefit": {"museum of science": "museum-of-science"}
    }), encoding="utf-8")

    from scripts.build_attractions_index import build_index
    idx = build_index(tmp_path / "raw", config_root=tmp_path / "config")
    assert "museum-of-science" in idx
    assert "cohasset" in idx["museum-of-science"]["sources"]


def test_museumkey_slug_used_when_already_canonical(tmp_path):
    """museumkey: if raw.slug is already in name_to_benefit.values(), prefer it."""
    mk = tmp_path / "raw" / "museumkey" / "index"
    mk.mkdir(parents=True)
    (mk / "hingham.json").write_text(json.dumps({
        "passes": [
            {"slug": "boston-childrens-museum",
             "museum_name": "Some Other Name That Won't Match",
             "status": "ok"},
        ],
    }), encoding="utf-8")
    cfg = tmp_path / "config" / "platform_pass_ids"
    cfg.mkdir(parents=True)
    (cfg / "museumkey.json").write_text(json.dumps({
        "name_to_benefit": {"boston children's museum": "boston-childrens-museum"}
    }), encoding="utf-8")

    from scripts.build_attractions_index import build_index
    idx = build_index(tmp_path / "raw", config_root=tmp_path / "config")
    assert "boston-childrens-museum" in idx
    assert "hingham" in idx["boston-childrens-museum"]["sources"]
