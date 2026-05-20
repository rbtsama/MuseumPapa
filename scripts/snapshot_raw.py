"""CLI: archive data/raw/ to data/snapshots/<date>/"""
from pathlib import Path
from malibbene.common.snapshot import archive_raw_to_snapshot

ROOT = Path(__file__).resolve().parent.parent

if __name__ == "__main__":
    result = archive_raw_to_snapshot(
        raw_root=ROOT / "data/raw",
        snapshot_root=ROOT / "data/snapshots",
    )
    print(result)
