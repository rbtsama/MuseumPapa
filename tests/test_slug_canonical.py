"""Schema lock: each duplicate slug pair must collapse to one canonical entity."""
import json


def test_no_duplicate_attraction_entities():
    """After build, none of the 9 legacy slugs should appear in attractions.json."""
    legacy = [
        "museum-of-fine-arts",
        "institute-of-contemporary-art-boston",
        "john-f-kennedy-library-and-museum",
        "the-trustees-of-the-reservations",
        "trustees-of-the-reservations",
        "plimoth-patuxet-museums",
        "american-rep-theater",
        "massachusetts-state-parks-department-of-conservation-and-recreation",
        "the-butterfly-place",
    ]
    attrs = json.load(open("data/structured/attractions.json", encoding="utf-8"))["attractions"]
    slugs = {a["slug"] for a in attrs}
    leaked = [s for s in legacy if s in slugs]
    assert not leaked, f"Legacy slugs still present in attractions.json: {leaked}"


def test_passes_use_canonical_only():
    """No pass row should reference a legacy slug."""
    legacy = {
        "museum-of-fine-arts", "institute-of-contemporary-art-boston",
        "john-f-kennedy-library-and-museum", "the-trustees-of-the-reservations",
        "trustees-of-the-reservations", "plimoth-patuxet-museums",
        "american-rep-theater",
        "massachusetts-state-parks-department-of-conservation-and-recreation",
        "the-butterfly-place",
    }
    passes = json.load(open("data/structured/passes.json", encoding="utf-8"))["passes"]
    bad = [p for p in passes if p["attraction_slug"] in legacy]
    assert not bad, f"{len(bad)} passes still reference legacy slugs"
