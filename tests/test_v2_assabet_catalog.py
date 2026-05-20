from pathlib import Path
from malibbene.sources_v2.assabet.catalog import parse_index_html

FIXT = Path(__file__).parent / "fixtures/assabet/wakefield_index.html"

def test_parse_index_returns_pass_list_with_required_fields():
    html = FIXT.read_text(encoding="utf-8")
    passes = parse_index_html(html, library_id="wakefield")
    assert len(passes) > 5
    p = passes[0]
    assert "attraction_slug" in p
    assert "benefit_text" in p
    assert "source_phrases" in p
    assert p["library_id"] == "wakefield"
