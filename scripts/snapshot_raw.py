"""CLI: archive data/raw/ to data/snapshots/<date>/"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from malibbene.common.snapshot import archive_raw_to_snapshot

if __name__ == "__main__":
    result = archive_raw_to_snapshot(
        raw_root=ROOT / "data/raw",
        snapshot_root=ROOT / "data/snapshots",
    )
    print(result)
