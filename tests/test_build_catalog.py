"""Test build_library_catalog: merge raw/<platform>/index + normalize."""
import json
from pathlib import Path

import pytest


@pytest.fixture
def fake_raw_root(tmp_path):
    assabet = tmp_path / "raw" / "assabet" / "index"
    assabet.mkdir(parents=True)
    (assabet / "wakefield.json").write_text(json.dumps({
        "scraped_at": "2026-05-13T16:07:09+00:00",
        "meta": {"status_summary": {"ok": 2, "empty": 0, "failed": {}, "total": 2, "ok_ratio": 1.0}},
        "passes": [
            {"slug": "mos", "museum_name": "Museum of Science",
             "address": "1 Science Park, Boston, MA 02114",
             "website": "https://www.mos.org/",
             "categories": ["Science"], "pass_type": "digital",
             "pass_type_raw": "Digital coupon",
             "benefits_text": "Free admission for up to 4 people.",
             "status": "ok"},
            {"slug": "neaq", "museum_name": "New England Aquarium",
             "address": "1 Central Wharf, Boston, MA 02110",
             "website": "https://www.neaq.org/", "categories": ["Ocean"],
             "pass_type": "physical-coupon",
             "pass_type_raw": "Coupon (pick up at library)",
             "benefits_text": "Pass admits up to 4 people for half price.",
             "status": "ok"},
        ],
    }), encoding="utf-8")
    return tmp_path / "raw"


def test_build_library_catalog_includes_normalized_label(fake_raw_root):
    from malibbene.build.catalog import build_library_catalog

    cat = build_library_catalog(fake_raw_root)

    assert "wakefield" in cat["libraries"]
    wake = cat["libraries"]["wakefield"]
    assert wake["platform"] == "assabet"
    assert "mos" in wake["passes"]
    mos = wake["passes"]["mos"]
    assert mos["pass_type"] == "digital"
    assert mos["benefit_class"] == "free"
    assert mos["benefit_label"].lower() == "free"
    neaq = wake["passes"]["neaq"]
    assert neaq["benefit_class"] == "half"


def test_build_library_catalog_attaches_availability(tmp_path):
    from malibbene.build.catalog import build_library_catalog

    assabet_idx = tmp_path / "raw" / "assabet" / "index"
    assabet_idx.mkdir(parents=True)
    (assabet_idx / "wakefield.json").write_text(json.dumps({
        "passes": [{"slug": "mos", "museum_name": "MOS", "pass_type": "digital",
                    "benefits_text": "Free.", "status": "ok"}]
    }), encoding="utf-8")
    assabet_avail = tmp_path / "raw" / "assabet" / "availability"
    assabet_avail.mkdir(parents=True)
    (assabet_avail / "wakefield.json").write_text(json.dumps({
        "passes": {"mos": {"status": "ok",
                            "calendar": {"2026-05-13": "available", "2026-05-14": "booked"}}}
    }), encoding="utf-8")

    cat = build_library_catalog(tmp_path / "raw")
    mos = cat["libraries"]["wakefield"]["passes"]["mos"]
    assert mos["calendar"]["2026-05-13"] == "available"
    assert mos["calendar"]["2026-05-14"] == "booked"


def test_build_library_catalog_handles_libcal_via_platform_map(tmp_path):
    from malibbene.build.catalog import build_library_catalog

    libcal = tmp_path / "raw" / "libcal" / "index"
    libcal.mkdir(parents=True)
    (libcal / "bpl.json").write_text(json.dumps({
        "passes": [{"pass_id": "abc123", "slug": "mos-libcal-side",
                    "museum_name": "MOS", "benefits_text": "Free.", "status": "ok",
                    "pass_type": "digital"}]
    }), encoding="utf-8")
    cfg = tmp_path / "config" / "platform_pass_ids"
    cfg.mkdir(parents=True)
    (cfg / "bpl.json").write_text(json.dumps({"passes": {"mos": "abc123"}}), encoding="utf-8")
    (cfg / "libcal.json").write_text(json.dumps({"libraries": {}}), encoding="utf-8")
    (cfg / "museumkey.json").write_text(json.dumps({"libraries": {}, "name_to_benefit": {}}), encoding="utf-8")

    cat = build_library_catalog(tmp_path / "raw", config_root=tmp_path / "config")
    assert "mos" in cat["libraries"]["bpl"]["passes"]


def test_build_library_catalog_writes_meta_summary(fake_raw_root):
    from malibbene.build.catalog import build_library_catalog

    cat = build_library_catalog(fake_raw_root)
    assert "_meta" in cat
    assert cat["_meta"]["n_libraries"] >= 1
    assert cat["_meta"]["n_passes_total"] >= 2
