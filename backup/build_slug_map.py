"""Auto-build SLUG_MAP for all 14 Assabet libraries by fetching each by-museum
index page and fuzzy-matching slugs to our canonical benefit IDs.

Output: prints a Python dict literal you paste into slug_map.py.
"""
import json
import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor

LIB_DOMAIN = {
    "wakefield":     "wakefieldlibrary.assabetinteractive.com",
    "stoneham":      "stonehamlibrary.assabetinteractive.com",
    "reading":       "readingpl.assabetinteractive.com",
    "woburn":        "woburnpubliclibrary.assabetinteractive.com",
    "lynnfield":     "lynnfieldlibrary.assabetinteractive.com",
    "peabody":       "peabodylibrary.assabetinteractive.com",
    "melrose":       "melrosepubliclibrary.assabetinteractive.com",
    "saugus":        "sauguspubliclibrary.assabetinteractive.com",
    "malden":        "maldenpubliclibrary.assabetinteractive.com",
    "medford":       "medfordlibrary.assabetinteractive.com",
    "burlington":    "burlington.assabetinteractive.com",
    "north-reading": "flintmemoriallibrary.assabetinteractive.com",
    "wilmington":    "wilmlibrary.assabetinteractive.com",
}

ALIASES = {
    "boston-childrens-museum":       ["boston-childrens-museum"],
    "boston-by-foot":                ["boston-by-foot"],
    "butterfly-place":               ["the-butterfly-place"],
    "childrens-piazza":              ["the-childrens-piazza"],
    "concord-museum":                ["concord-museum"],
    "davis-farmland":                ["davis-farmland"],
    "discovery-museum":              ["the-discovery-museums", "the-discovery-museum"],
    "ecotarium":                     ["ecotarium"],
    "einsteins-workshop":            ["einsteins-workshop"],
    "garden-in-the-woods":           ["garden-in-the-woods-native-plant-trust"],
    "gore-place":                    ["gore-place"],
    "greater-boston-stage":          ["greater-boston-stage-company"],
    "griffin-museum":                ["griffin-museum-of-photography"],
    "harvard-art-museums":           ["harvard-art-museums"],
    "harvard-museums":               ["harvard-museums-of-science-and-culture", "harvard-museum-of-natural-history"],
    "historic-new-england":          ["historic-new-england"],
    "house-of-seven-gables":         ["the-house-of-seven-gables"],
    "ica-boston":                    ["institute-of-contemporary-art-boston"],
    "isabella-stewart-gardner":      ["isabella-stewart-gardner-museum"],
    "jfk-library":                   ["john-f-kennedy-library-and-museum"],
    "ma-state-parks":                ["massachusetts-state-parks-department-of-conservation-and-recreation"],
    "american-heritage-museum":      ["american-heritage-museum"],
    "mass-audubon":                  ["mass-audubon", "mass-audubon-drumlin-farm"],
    "merrimack-rep":                 ["merrimack-repertory-theatre"],
    "mfa":                           ["museum-of-fine-arts"],
    "museum-of-science":             ["museum-of-science"],
    "naismith-basketball-hof":       ["naismith-memorial-basketball-hall-of-fame"],
    "new-england-aquarium":          ["new-england-aquarium"],
    "new-england-botanic-garden":    ["new-england-botanic-garden-at-tower-hill"],
    "new-england-quilt-museum":      ["new-england-quilt-museum"],
    "north-shore-childrens-museum":  ["north-shore-childrens-museum"],
    "paddle-boston":                 ["paddle-boston"],
    "patriots-hall-of-fame":         ["patriots-hall-of-fame"],
    "paul-revere-house":             ["paul-revere-house"],
    "peabody-essex-museum":          ["peabody-essex-museum"],
    "plimoth-patuxet":               ["plimoth-patuxet-museums"],
    "salem-witch-museum":            ["salem-witch-museum"],
    "sandmagination":                ["sandmagination"],
    "trustees-of-reservations":      ["the-trustees-of-the-reservations", "trustees-of-the-reservations"],
    "uss-constitution-museum":       ["the-uss-constitution-museum"],
    "wenham-museum":                 ["wenham-museum"],
    "zoo-new-england":               ["zoo-new-england"],
    "american-rep-theater":          ["american-repertory-theater"],
    "aviation-museum-nh":            ["the-aviation-museum-of-new-hampshire", "aviation-museum-of-new-hampshire"],
}


def fetch_slugs(lib_id: str, domain: str) -> tuple[str, set[str]]:
    url = f"https://{domain}/museum-passes/by-museum/"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  [err {e}] {lib_id}", file=sys.stderr)
        return lib_id, set()
    return lib_id, set(re.findall(r'/museum-passes/by-museum/([a-z0-9][a-z0-9\-]*)/', html))


def main():
    lib_slugs: dict[str, set[str]] = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        for lib_id, slugs in pool.map(lambda kv: fetch_slugs(*kv), LIB_DOMAIN.items()):
            lib_slugs[lib_id] = slugs

    out: dict[str, dict[str, str]] = {}
    for benefit_id, candidates in ALIASES.items():
        per_lib = {}
        for lib_id, slugs in lib_slugs.items():
            for cand in candidates:
                if cand in slugs:
                    per_lib[lib_id] = cand
                    break
        if per_lib:
            out[benefit_id] = per_lib

    print(f"# {sum(len(v) for v in out.values())} (library,attraction) pairs across "
          f"{len(out)} attractions and {len(lib_slugs)} libraries")
    print("SLUG_MAP = {")
    for bid in sorted(out):
        per_lib = out[bid]
        parts = ", ".join(f'"{l}": "{s}"' for l, s in sorted(per_lib.items()))
        print(f'    "{bid}": {{{parts}}},')
    print("}")


if __name__ == "__main__":
    main()
