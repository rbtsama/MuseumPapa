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


def test_parse_index_extracts_and_classifies_pass_type():
    """The index page carries each pass's type in a `museum-pass-pass-type`
    block. The scraper must populate raw text AND a classified value matching
    the three canonical pass types (digital / physical-coupon / physical-circ).
    Regression for the bug where every pass_type came out None."""
    html = FIXT.read_text(encoding="utf-8")
    by_slug = {p["attraction_slug"]: p for p in parse_index_html(html, library_id="wakefield")}
    pem = by_slug["peabody-essex-museum"]
    assert pem["pass_type_text"], "raw pass type text not extracted"
    assert pem["pass_type"] == "digital"
    assert by_slug["the-house-of-seven-gables"]["pass_type"] == "physical-coupon"
    # every pass gets a classified value (never None)
    assert all(p["pass_type"] for p in by_slug.values())
