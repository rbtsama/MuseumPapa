from pathlib import Path
from malibbene.sources_v2.libcal.catalog import parse_libcal_index


def test_parse_libcal_extracts_passes():
    html = (Path(__file__).parent / "fixtures/libcal/bpl_index.html").read_text(encoding="utf-8")
    passes = parse_libcal_index(html, library_id="bpl")
    assert len(passes) >= 10
    assert all("attraction_slug" in p and "title" in p for p in passes)


def test_parse_libcal_dedupes_pass_ids():
    html = (Path(__file__).parent / "fixtures/libcal/bpl_index.html").read_text(encoding="utf-8")
    passes = parse_libcal_index(html, library_id="bpl")
    ids = [p["libcal_pass_id"] for p in passes]
    assert len(ids) == len(set(ids))


def test_parse_libcal_handles_slug_ids():
    html = (Path(__file__).parent / "fixtures/libcal/cambridge_index.html").read_text(encoding="utf-8")
    passes = parse_libcal_index(html, library_id="cambridge")
    assert len(passes) >= 10
    assert any(not p["libcal_pass_id"].isdigit() for p in passes)
