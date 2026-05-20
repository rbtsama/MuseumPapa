from pathlib import Path

from malibbene.sources_v2.museumkey.catalog import parse_museumkey_index


def test_parse_returns_passes_with_id_and_name():
    html = (
        Path(__file__).parent / "fixtures/museumkey/cohasset_index.html"
    ).read_text(encoding="utf-8")
    passes = parse_museumkey_index(html, library_id="cohasset")
    assert len(passes) >= 5
    assert all("attraction_slug" in p and "title" in p for p in passes)
