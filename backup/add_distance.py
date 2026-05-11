import json
from pathlib import Path

ROOT = Path(__file__).parent
DATA_FILE = ROOT / "library-data.json"
data = json.loads(DATA_FILE.read_text())

DRIVE_MIN_FROM_WAKEFIELD = {
    "greater-boston-stage":        5,
    "north-shore-childrens-museum": 15,
    "zoo-new-england":             10,
    "wenham-museum":               25,
    "peabody-essex-museum":        20,
    "house-of-seven-gables":       25,
    "salem-witch-museum":          25,
    "trustees-of-reservations":    20,
    "mass-audubon":                25,
    "ma-state-parks":              25,
    "griffin-museum":              10,
    "harvard-museums":             20,
    "harvard-art-museums":         20,
    "royall-house":                15,
    "historic-new-england":        20,
    "paddle-boston":               25,
    "boston-by-foot":              30,
    "boston-childrens-museum":     30,
    "museum-of-science":           25,
    "new-england-aquarium":        30,
    "uss-constitution-museum":     25,
    "boston-harbor-islands":       30,
    "mfa":                         30,
    "isabella-stewart-gardner":    30,
    "ica-boston":                  35,
    "jfk-library":                 35,
    "paul-revere-house":           30,
    "revolutionary-spaces":        30,
    "greenway-carousel":           30,
    "mapparium":                   30,
    "larz-anderson":               30,
    "boch-center":                 30,
    "american-rep-theater":        25,
    "concord-museum":              30,
    "discovery-museum":            35,
    "garden-in-the-woods":         35,
    "gore-place":                  25,
    "butterfly-place":             40,
    "einsteins-workshop":          30,
    "merrimack-rep":               40,
    "aviation-museum-nh":          50,
    "sandmagination":              45,
    "childrens-piazza":            35,
    "davis-farmland":              60,
    "american-heritage-museum":    45,
    "new-england-quilt-museum":    35,
    "new-england-botanic-garden":  60,
    "ecotarium":                   60,
    "plimoth-patuxet":             65,
    "sandwich-glass":              90,
    "naismith-basketball-hof":     90,
    "patriots-hall-of-fame":       40,
}

missing = [b["id"] for b in data["benefits"] if b["id"] not in DRIVE_MIN_FROM_WAKEFIELD]
if missing:
    print("WARNING — no distance for:", missing)

for b in data["benefits"]:
    b["drive_min_from_wakefield"] = DRIVE_MIN_FROM_WAKEFIELD.get(b["id"])

DATA_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))
print(f"updated {len(data['benefits'])} benefits with drive times")
print("nearest 5:")
for b in sorted(data["benefits"], key=lambda x: x.get("drive_min_from_wakefield") or 999)[:5]:
    print(f"  {b['drive_min_from_wakefield']:>3} min — {b['name']}")
print("farthest 5:")
for b in sorted(data["benefits"], key=lambda x: x.get("drive_min_from_wakefield") or 999)[-5:]:
    print(f"  {b['drive_min_from_wakefield']:>3} min — {b['name']}")
