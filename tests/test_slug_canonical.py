"""Unit tests for attraction slug canonicalization.

Covers: suffix stripping, hand-verified spelling-variant merges, the legacy
auto-loaded alias map, and — critically — that DANGER pairs of distinct
real-world entities stay DISTINCT (never silently merged).
"""
import json
import pathlib

from malibbene.build.slug_canonical import (
    LEGACY_TO_CANONICAL,
    canonical,
    _legacy_map,
)

DATA_DIR = pathlib.Path(__file__).resolve().parents[1] / "data" / "structured"


# --------------------------------------------------------------------------
# (a) suffix stripping
# --------------------------------------------------------------------------
def test_suffix_strip_to_legacy_canonical():
    # `-e-coupon` etc. strip down to a base that resolves to a canonical slug.
    assert canonical("new-england-aquarium-e-coupon") == "new-england-aquarium"
    assert canonical("museum-of-science-e-ticket") == "museum-of-science"
    assert canonical("uss-constitution-museum-e-coupon") == "uss-constitution-museum"
    assert canonical("isabella-stewart-gardner-museum-promo-code") == "isabella-stewart-gardner-museum"
    assert canonical("sandwich-glass-museum-digital-coupon-pass") == "sandwich-glass-museum"
    assert canonical("revolutionary-spaces-physical-pass") == "revolutionary-spaces"
    assert canonical("zoo-new-england-physical-pass") == "zoo-new-england"
    assert canonical("hale-education-physical-pass") == "hale-education"


def test_suffix_strip_then_handmap():
    # Strip the variant suffix, then the stripped base goes through the hand map.
    assert canonical("boston-children-s-museum-e-coupon") == "boston-childrens-museum"
    assert canonical("institute-of-contemporary-art-e-coupon") == "ica-boston"
    assert canonical("the-greenway-carousel-e-coupon") == "greenway-carousel"
    assert canonical("trustees-go-pass-physical-pass") == "trustees-of-reservations"
    assert canonical("dcr-parkspass-physical-pass") == "ma-state-parks"
    assert canonical("larz-anderson-museum-physical-pass") == "larz-anderson"
    assert canonical("tacc-x-paddle-boston-coupon-code") == "paddle-boston"


def test_suffix_not_stripped_when_base_unknown():
    # An unknown slug whose "stripped" base also doesn't resolve stays itself.
    assert canonical("totally-made-up-attraction-digital") == "totally-made-up-attraction-digital"


# --------------------------------------------------------------------------
# (b) hand-verified spelling variants
# --------------------------------------------------------------------------
def test_handmap_spelling_variants():
    assert canonical("museum-of-fine-arts-boston") == "mfa"
    assert canonical("museum-of-fine-arts") == "mfa"
    assert canonical("institute-of-contemporary-art") == "ica-boston"
    assert canonical("john-f-kennedy-presidential-library-and-museum") == "jfk-library"
    assert canonical("american-repertory-theatre") == "american-repertory-theater"
    assert canonical("american-repertory-theater-at-harvard-university") == "american-repertory-theater"
    assert canonical("harvard-museums-of-science-culture") == "harvard-museums-of-science-and-culture"
    assert canonical("boston-children-s-museum") == "boston-childrens-museum"
    assert canonical("children-s-museum-easton") == "childrens-museum-easton"
    assert canonical("heritage-museums-and-gardens") == "heritage-museums-gardens"
    assert canonical("plimoth-patuxet-museums") == "plimoth-patuxet"
    assert canonical("the-trustees") == "trustees-of-reservations"
    assert canonical("trustees-go-pass") == "trustees-of-reservations"


def test_state_parks_variants_collapse():
    for s in (
        "dcr-massachusetts-state-parks",
        "massachusetts-state-parks",
        "massachusetts-parkspass",
    ):
        assert canonical(s) == "ma-state-parks", s


def test_mapparium_variants_collapse():
    assert canonical("how-do-you-see-the-world-experience-mapparium") == "mapparium"
    assert canonical("how-do-you-see-the-world-mapparium-globe") == "mapparium"


# --------------------------------------------------------------------------
# (c) DANGER — distinct entities must STAY distinct
# --------------------------------------------------------------------------
def test_three_distinct_harvard_institutions():
    a = canonical("harvard-art-museums")
    b = canonical("harvard-museums-of-science-and-culture")
    c = canonical("harvard-museum-of-natural-history")
    assert len({a, b, c}) == 3, (a, b, c)


def test_mass_audubon_org_vs_sanctuaries_distinct():
    org = canonical("mass-audubon")
    drumlin = canonical("mass-audubon-drumlin-farm")
    sanctuary = canonical("mass-audubon-wildlife-sanctuary")
    assert len({org, drumlin, sanctuary}) == 3, (org, drumlin, sanctuary)


def test_boston_harbor_ferry_vs_islands_distinct():
    # The `-ferry` suffix must NOT collapse the ferry onto the islands park.
    ferry = canonical("boston-harbor-islands-ferry")
    islands = canonical("boston-harbor-islands")
    assert ferry == "boston-harbor-island-ferry"
    assert islands == "boston-harbor-islands"
    assert ferry != islands


def test_paul_revere_heritage_site_vs_house_distinct():
    assert canonical("paul-revere-heritage-site") != canonical("paul-revere-house")


# --------------------------------------------------------------------------
# legacy auto map sanity
# --------------------------------------------------------------------------
def test_legacy_map_loads_and_aliases_resolve():
    lm = _legacy_map()
    assert lm, "legacy alias map should be non-empty"
    # a record's own slug maps to itself
    assert lm.get("mfa") == "mfa"
    # legacy_slugs alias resolves via canonical()
    assert canonical("museum-of-fine-arts") == "mfa"


# --------------------------------------------------------------------------
# post-build invariants (require a build to have run)
# --------------------------------------------------------------------------
def test_no_legacy_slug_leaks_into_attractions():
    f = DATA_DIR / "attractions.json"
    if not f.exists():
        return
    attrs = json.loads(f.read_text(encoding="utf-8"))["attractions"]
    slugs = {a["slug"] for a in attrs}
    leaked = sorted(set(LEGACY_TO_CANONICAL) & slugs)
    # self-mapping entries (slug == canonical) are allowed
    leaked = [s for s in leaked if LEGACY_TO_CANONICAL[s] != s]
    assert not leaked, f"Legacy slugs still present in attractions.json: {leaked}"


def test_passes_use_canonical_only():
    f = DATA_DIR / "passes.json"
    if not f.exists():
        return
    passes = json.loads(f.read_text(encoding="utf-8"))["passes"]
    bad = [p for p in passes if p["attraction_slug"] != canonical(p["attraction_slug"])]
    assert not bad, f"{len(bad)} passes reference non-canonical slugs"
