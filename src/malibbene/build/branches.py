from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, timezone
from malibbene.common.audit_overrides import load_overrides, apply_overrides

def build_branches(raw_root: Path, overrides_root: Path, out_path: Path) -> dict:
    branches_dir = raw_root/"libcal"/"branches"
    overrides = load_overrides(overrides_root)
    out_branches = []
    if branches_dir.exists():
        for f in branches_dir.glob("*.json"):
            data = json.loads(f.read_text())
            for b in data.get("branches",[]):
                key = f"{b['library_id']}__{b['id'].replace(b['library_id']+'-','')}"
                b = apply_overrides(f"branch:{key}", b, overrides)
                out_branches.append(b)
    out = {"_meta":{"built_at":datetime.now(timezone.utc).isoformat(),
                    "n_branches":len(out_branches)},
           "branches": out_branches}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    return out
