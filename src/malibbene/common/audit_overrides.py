from __future__ import annotations
import json
from pathlib import Path
from typing import Any

def load_overrides(overrides_root: Path) -> dict[str, dict]:
    """Scan overrides_root, index by 'entity:id:field'.

    Directory layout:
        libraries/<id>/<field>.json
        attractions/<slug>/<field>.json
        passes/<lib>__<slug>/<field>.json
        branches/<lib>__<branch>/<field>.json
    """
    by_target: dict[str, dict] = {}
    if not overrides_root.exists():
        return by_target
    kind_map = {"libraries": "library", "attractions": "attraction",
                "passes": "pass", "branches": "branch"}
    for entity_dir, kind in kind_map.items():
        base = overrides_root / entity_dir
        if not base.exists():
            continue
        for id_dir in base.iterdir():
            if not id_dir.is_dir():
                continue
            for field_file in id_dir.glob("*.json"):
                target = f"{kind}:{id_dir.name}:{field_file.stem}"
                by_target[target] = json.loads(field_file.read_text())
    return by_target

def apply_overrides(entity_prefix: str, raw: dict, overrides: dict[str, dict]) -> dict:
    """raw is one entity's dict; entity_prefix is 'library:wakefield'."""
    out = dict(raw)
    for target, record in overrides.items():
        if not target.startswith(entity_prefix + ":"):
            continue
        if record.get("status") != "corrected":
            continue
        field = target.split(":", 2)[2]
        out[field] = record["corrected_value"]
    return out
