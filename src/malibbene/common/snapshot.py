from __future__ import annotations
import shutil
from pathlib import Path
from datetime import date

def archive_raw_to_snapshot(
    raw_root: Path,
    snapshot_root: Path,
    snapshot_date: str | None = None,
) -> dict:
    if snapshot_date is None:
        snapshot_date = date.today().isoformat()
    target = snapshot_root / snapshot_date
    if target.exists():
        raise FileExistsError(f"snapshot already exists: {target}")

    target.mkdir(parents=True)
    files_copied = 0
    for src in raw_root.rglob("*"):
        if src.is_file():
            rel = src.relative_to(raw_root)
            dst = target / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            files_copied += 1
    return {"snapshot_date": snapshot_date, "snapshot_path": str(target), "files_copied": files_copied}
