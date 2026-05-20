"""List pending LLM extractions. Each line is one JSON record for controller dispatch.

Subagent contract:
  1. Read prompt_template + html_path
  2. Extract
  3. Write data/raw/attractions/<target_kind>/<slug>.json:
     {"status":"ok","extracted":{...}} or {"status":"failed","error":...}
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PENDING = ROOT/"data/raw/attractions/_pending"

def main():
    if not PENDING.exists():
        print("no pending"); return
    for f in PENDING.rglob("*.json"):
        req = json.loads(f.read_text(encoding="utf-8"))
        if req.get("status") != "pending":
            continue
        out_path = ROOT/"data/raw/attractions"/req["target_kind"]/f"{req['slug']}.json"
        if out_path.exists():
            continue
        print(json.dumps({
            "request_file": str(f), "target_kind": req["target_kind"],
            "slug": req["slug"], "html_path": req["html_path"],
            "output_path": str(out_path),
        }))

if __name__ == "__main__":
    main()
