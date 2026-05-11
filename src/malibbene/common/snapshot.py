"""Snapshot raw scraper outputs into ``data/snapshots/<YYYY-MM-DD>/``.

Used to detect new/removed museum passes by diffing today's index pages
against a prior snapshot (see BRD §6.1 'New景点/新合作发现').
"""

from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = REPO_ROOT / "data" / "raw"
SNAPSHOTS_DIR = REPO_ROOT / "data" / "snapshots"


def archive_path(rel_path: str | Path, snapshot_date: date | None = None) -> Path:
    d = (snapshot_date or date.today()).isoformat()
    return SNAPSHOTS_DIR / d / rel_path


def archive(rel_path: str | Path, snapshot_date: date | None = None) -> Path | None:
    """Move the current ``data/raw/<rel_path>`` into today's snapshot folder.

    Returns the destination path, or ``None`` if the source file did not exist.
    """
    src = RAW_DIR / rel_path
    if not src.exists():
        return None
    dst = archive_path(rel_path, snapshot_date)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return dst


def latest_prior(rel_path: str | Path) -> Path | None:
    """Return the most recent snapshot of ``rel_path`` strictly before today."""
    today = date.today().isoformat()
    candidates = []
    if not SNAPSHOTS_DIR.exists():
        return None
    for d in SNAPSHOTS_DIR.iterdir():
        if not d.is_dir() or d.name >= today:
            continue
        f = d / rel_path
        if f.exists():
            candidates.append(f)
    if not candidates:
        return None
    return sorted(candidates, key=lambda p: p.parent.name)[-1]
