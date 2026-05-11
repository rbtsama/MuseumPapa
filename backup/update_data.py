import json
from pathlib import Path

ROOT = Path(__file__).parent
DATA_FILE = ROOT / "library-data.json"
data = json.loads(DATA_FILE.read_text())

POLICIES = {
    "wakefield":     ("open_ma_resident", "NOBLE network. Free card for any MA resident with photo ID + proof of address."),
    "stoneham":      ("open_ma_resident", "NOBLE network. Free card for any MA resident with photo ID + proof of address. Non-NOBLE cards can also be added."),
    "reading":       ("open_ma_resident", "NOBLE network. Free card for any MA resident."),
    "woburn":        ("residents_only",   "Museum passes restricted to Woburn residents only — even network cardholders cannot reserve."),
    "lynnfield":     ("open_ma_resident", "Free card for any MA resident. eCard must be upgraded to full-access (in person) before reserving museum passes."),
    "peabody":       ("open_ma_resident", "NOBLE network. Free card for any MA resident with proof of address."),
    "melrose":       ("residents_only",   "Passes restricted to Melrose residents (limited exception for City of Melrose staff/retirees)."),
    "winchester":    ("residents_only",   "Passes available to Winchester residents only (with a Minuteman card). One household = 2 passes/week."),
    "saugus":        ("open_ma_resident", "NOBLE network. Any NOBLE card in good standing can reserve. ParksPass also requires MA residency."),
    "malden":        ("residents_only",   "Anyone (MA resident) can get a Malden card, but museum-pass program is restricted to Malden residents only."),
    "medford":       ("residents_only",   "Museum passes generally tied to Medford residents / home library — non-residents should call to confirm."),
    "burlington":    ("network_only",     "MVLC network. Any MVLC cardholder can reserve. Non-MVLC need Burlington work/school/property to get a card."),
    "north-reading": ("open_ma_resident", "NOBLE network (Flint Memorial). Any NOBLE cardholder can reserve passes; pickup at 1st-floor circulation."),
    "wilmington":    ("network_only",     "MVLC network. MA residents from certified towns can get a free MVLC eCard online via Wilmington — full-service, can reserve passes. Non-MVLC residents only get 30-day temp card."),
}

for lib in data["libraries"]:
    pol, note = POLICIES[lib["id"]]
    lib["non_resident_policy"] = pol
    existing = lib.get("notes", "")
    lib["notes"] = note + (f" {existing}" if existing and existing not in note else "")

bpl = {
    "id": "bpl",
    "name": "Boston Public Library",
    "town": "Boston",
    "pass_page": "https://www.bpl.org/museum-passes/",
    "non_resident_policy": "open_ma_resident",
    "notes": "Open to any MA resident. eCard issued online for digital resources only — physical card (free, in person at any branch) required for museum passes."
}
wakefield_idx = next(i for i, l in enumerate(data["libraries"]) if l["id"] == "wakefield")
data["libraries"].insert(wakefield_idx + 1, bpl)

new_benefits = [
    {"id": "greenway-carousel",   "name": "Greenway Carousel",                        "kid_focused": True,  "category": "kids",    "official_url": "https://www.rosekennedygreenway.org/the-carousel/"},
    {"id": "mapparium",           "name": "Mary Baker Eddy Library / Mapparium",      "kid_focused": True,  "category": "kids",    "official_url": "https://www.marybakereddylibrary.org/project/mapparium/"},
    {"id": "larz-anderson",       "name": "Larz Anderson Auto Museum",                "kid_focused": True,  "category": "kids",    "official_url": "https://larzanderson.org/"},
    {"id": "revolutionary-spaces","name": "Revolutionary Spaces (Old State House)",   "kid_focused": False, "category": "general", "official_url": "https://revolutionaryspaces.org/"},
    {"id": "sandwich-glass",      "name": "Sandwich Glass Museum",                    "kid_focused": False, "category": "general", "official_url": "https://sandwichglassmuseum.org/"},
    {"id": "boch-center",         "name": "Boch Center Tours",                        "kid_focused": False, "category": "other",   "official_url": "https://www.bochcenter.org/"},
]
existing_ids = {b["id"] for b in data["benefits"]}
for nb in new_benefits:
    if nb["id"] not in existing_ids:
        data["benefits"].append(nb)

bpl_matrix = {
    "american-rep-theater":     {"value": "Free",       "note": "2 tickets, email ticketservices@amrep.org"},
    "boch-center":              {"value": "Free",       "note": "4 tickets, coupon code via bochcenter.org/tours"},
    "boston-childrens-museum":  {"value": "$12",        "note": "$12/person, up to 4 (under 1 free)"},
    "boston-harbor-islands":    {"value": "Half-price", "note": "50% off ferry, group of 2 or 4"},
    "ma-state-parks":           {"value": "Free",       "note": "free parking hangtag, one per month"},
    "greenway-carousel":        {"value": "Free",       "note": "up to 4 riders, one ride"},
    "harvard-museums":          {"value": "Free",       "note": "up to 4 visitors, physical pass"},
    "mapparium":                {"value": "Free",       "note": "up to 4 adults; under 17 always free"},
    "ica-boston":               {"value": "$10",        "note": "$10/ticket, up to 2 (e-coupon)"},
    "isabella-stewart-gardner": {"value": "$5",         "note": "$5/adult, up to 4; under 18 free"},
    "larz-anderson":            {"value": "Free",       "note": "up to 4 people, physical pass"},
    "mass-audubon":             {"value": "$2",         "note": "$2/visitor, up to 4 (under 2 free)"},
    "mfa":                      {"value": "$15",        "note": "$15/person, 2 adults + 4 youth (7-17)"},
    "museum-of-science":        {"value": "Free",       "note": "free exhibit halls, up to 4 (BPL is FREE vs half-price elsewhere)"},
    "new-england-aquarium":     {"value": "Free",       "note": "free admission, up to 4 (BPL is FREE vs half-price elsewhere)"},
    "peabody-essex-museum":     {"value": "$12",        "note": "$12/adult, up to 2 adults"},
    "revolutionary-spaces":     {"value": "Free",       "note": "2 adults + 2 children, physical pass"},
    "sandwich-glass":           {"value": "Half-price", "note": "50% off, up to 2 adults; no booking required"},
    "paddle-boston":            {"value": "Free",       "note": "1 boat rental (1-5 ppl depending on vessel)"},
    "trustees-of-reservations": {"value": "Discount",   "note": "Trustees GO Pass — family-membership rate"},
    "uss-constitution-museum":  {"value": "Free",       "note": "up to 9 guests"},
    "zoo-new-england":          {"value": "$9",         "note": "$9 adult / $6 child, up to 6, one booking/month"},
}
data["matrix"]["bpl"] = bpl_matrix

DATA_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))

print(f"libraries: {len(data['libraries'])}")
print(f"benefits:  {len(data['benefits'])}")
print(f"matrix cells: {sum(len(v) for v in data['matrix'].values())}")
print(f"bpl cells: {len(bpl_matrix)}")
json.loads(DATA_FILE.read_text())
print("JSON valid.")
