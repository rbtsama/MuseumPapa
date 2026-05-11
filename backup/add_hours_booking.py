import json
from pathlib import Path

ROOT = Path(__file__).parent
data = json.loads((ROOT / "library-data.json").read_text())
hb = json.loads((ROOT / "hours-booking.json").read_text())

VALID = {"walk_in", "recommended", "required", "promo_code", "timed_tour", "seasonal"}
counts = {}
for b in data["benefits"]:
    entry = hb[b["id"]]
    assert entry["booking_model"] in VALID, f"bad model for {b['id']}: {entry['booking_model']}"
    b["hours_summary"] = entry["hours_summary"]
    b["closed_days"] = entry["closed_days"]
    b["booking_model"] = entry["booking_model"]
    b["booking_note"] = entry["booking_note"]
    counts[entry["booking_model"]] = counts.get(entry["booking_model"], 0) + 1

(ROOT / "library-data.json").write_text(json.dumps(data, indent=2, ensure_ascii=False))
print(f"updated {len(data['benefits'])} benefits")
for k, v in sorted(counts.items(), key=lambda x: -x[1]):
    print(f"  {k:15s} {v}")
