from __future__ import annotations
import json
from pathlib import Path
from typing import Any

CONSOLIDATED_FILE = "audit_overrides.json"

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
    # Consolidated file written by the admin panel ({target: record}); overlays
    # (wins over) the legacy per-field directory tree above.
    consolidated = overrides_root / CONSOLIDATED_FILE
    if consolidated.exists():
        for target, record in json.loads(consolidated.read_text()).items():
            by_target[target] = record
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

def merge_override(store: dict[str, dict], record: dict) -> dict[str, dict]:
    """Upsert one audit record into a {target: record} store. Mutates and returns store."""
    target = record.get("target")
    if not target:
        raise ValueError("override record missing 'target'")
    store[target] = record
    return store

def remove_override(store: dict[str, dict], target: str) -> dict[str, dict]:
    """Remove a record by target. No-op if absent. Mutates and returns store."""
    store.pop(target, None)
    return store
