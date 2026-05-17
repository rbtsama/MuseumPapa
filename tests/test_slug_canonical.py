"""Schema lock: each duplicate slug pair must collapse to one canonical entity."""
import json
import pathlib

from malibbene.build.slug_canonical import LEGACY_TO_CANONICAL

DATA_DIR = pathlib.Path(__file__).resolve().parents[1] / "data" / "structured"


def test_no_duplicate_attraction_entities():
    """After build, no legacy slug should appear in attractions.json."""
    legacy = set(LEGACY_TO_CANONICAL.keys())
    with open(DATA_DIR / "attractions.json", encoding="utf-8") as f:
        attrs = json.load(f)["attractions"]
    slugs = {a["slug"] for a in attrs}
    leaked = sorted(legacy & slugs)
    assert not leaked, f"Legacy slugs still present in attractions.json: {leaked}"


def test_passes_use_canonical_only():
    """No pass row should reference a legacy slug."""
    legacy = set(LEGACY_TO_CANONICAL.keys())
    with open(DATA_DIR / "passes.json", encoding="utf-8") as f:
        passes = json.load(f)["passes"]
    bad = [p for p in passes if p["attraction_slug"] in legacy]
    assert not bad, f"{len(bad)} passes still reference legacy slugs"
