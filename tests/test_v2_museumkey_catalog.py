from pathlib import Path

from malibbene.sources_v2.museumkey.catalog import parse_museumkey_index


def test_parse_returns_passes_with_id_and_name():
    html = (
        Path(__file__).parent / "fixtures/museumkey/cohasset_index.html"
    ).read_text(encoding="utf-8")
    passes = parse_museumkey_index(html, library_id="cohasset")
    assert len(passes) >= 5
    assert all("attraction_slug" in p and "title" in p for p in passes)


def test_parse_extracts_benefit_text_from_detail_blocks():
    """detail<musid> div on the index page already carries per-pass benefit text
    (50% discount, free admission, etc.) — extract it so the coupon LLM
    pipeline has something to work with.
    """
    html = (
        Path(__file__).parent / "fixtures/museumkey/cohasset_index.html"
    ).read_text(encoding="utf-8")
    passes = parse_museumkey_index(html, library_id="cohasset")
    by_slug = {p["attraction_slug"]: p for p in passes}

    # Every pass should have non-empty benefit text from the fixture.
    n_with = sum(1 for p in passes if p.get("benefit_text"))
    assert n_with == len(passes), f"only {n_with}/{len(passes)} have benefit_text"

    # Spot-check a couple of known phrases (verified from fixture).
    harbor = by_slug["boston-harbor-island-ferry"]["benefit_text"]
    assert "50% discount" in harbor
    assert "up to 4 people" in harbor
    # Leading "66 Long Wharf ... Get Directions" must be stripped.
    assert not harbor.lower().startswith("66 long wharf")

    butterfly = by_slug["the-butterfly-place"]["benefit_text"]
    assert "admits 1 person for free" in butterfly.lower()
    # Trailing CTA / "Learn More" stripped.
    assert not butterfly.lower().endswith("learn more")

    # source_phrases mirrors benefit_text so enqueue_coupons picks it up.
    assert by_slug["boston-harbor-island-ferry"]["source_phrases"] == [harbor]


def test_parse_mk2_theme_extracts_benefit_text():
    """Hingham uses the MK2 layout (mk2ButtonName + forward musID link, and a
    'Visit museum website' link sits between address and benefit). Verify the
    cleanup pipeline handles it.
    """
    html = (
        Path(__file__).parent / "fixtures/museumkey/hingham_index.html"
    ).read_text(encoding="utf-8")
    passes = parse_museumkey_index(html, library_id="hingham")
    assert len(passes) >= 5
    n_with = sum(1 for p in passes if p.get("benefit_text"))
    assert n_with == len(passes), f"only {n_with}/{len(passes)} have benefit_text"

    by_slug = {p["attraction_slug"]: p for p in passes}
    aq = by_slug.get("new-england-aquarium")
    assert aq is not None and aq["benefit_text"], "missing NEA pass"
    # Real benefit phrase should survive cleanup; address/CTA prefix should not.
    assert "50% discount" in aq["benefit_text"]
    assert not aq["benefit_text"].lower().startswith("1 central wharf")
    assert not aq["benefit_text"].lower().startswith("visit museum website")
