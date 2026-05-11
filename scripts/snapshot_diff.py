"""Snapshot today's Assabet/BPL index files and diff against the prior snapshot.

Reports new/removed museum passes since the last snapshot — used to catch
when a library adds or drops a museum from its program. BRD §6.1 calls this
out as a maintenance signal we explicitly want.

Workflow:

  1. For each ``data/raw/{assabet/index,bpl/index.json}`` file we know about,
     copy it into ``data/snapshots/<YYYY-MM-DD>/<same relative path>``.
  2. Compare today's files against the latest prior snapshot (if any).
  3. Write a Markdown report to ``data/changelog/<YYYY-MM-DD>.md`` listing
     added / removed slugs per library.

Re-running on the same day is a no-op: today's snapshot dir already exists.
"""

from __future__ import annotations

import json
import shutil
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "data" / "raw"
SNAPSHOTS_DIR = REPO_ROOT / "data" / "snapshots"
CHANGELOG_DIR = REPO_ROOT / "data" / "changelog"


def index_files() -> list[Path]:
    """All raw files we treat as 'index' for diffing."""
    out: list[Path] = []
    assabet_index_dir = RAW_DIR / "assabet" / "index"
    if assabet_index_dir.exists():
        out.extend(sorted(assabet_index_dir.glob("*.json")))
    bpl_index = RAW_DIR / "bpl" / "index.json"
    if bpl_index.exists():
        out.append(bpl_index)
    return out


def snapshot_today() -> Path:
    today = date.today().isoformat()
    today_dir = SNAPSHOTS_DIR / today
    for src in index_files():
        rel = src.relative_to(RAW_DIR)
        dst = today_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    return today_dir


def latest_prior(today: str) -> Path | None:
    if not SNAPSHOTS_DIR.exists():
        return None
    prior_dirs = sorted(
        [d for d in SNAPSHOTS_DIR.iterdir() if d.is_dir() and d.name < today]
    )
    return prior_dirs[-1] if prior_dirs else None


def slugs_of(path: Path) -> set[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if "passes" in data and isinstance(data["passes"], list):
        return {
            p.get("slug") or p.get("pass_id") or "?"
            for p in data["passes"]
        }
    return set()


def diff_index_files(today_dir: Path, prior_dir: Path) -> list[dict]:
    rows: list[dict] = []
    today_files = {p.relative_to(today_dir): p for p in today_dir.rglob("*.json")}
    prior_files = {p.relative_to(prior_dir): p for p in prior_dir.rglob("*.json")}
    for rel in sorted(set(today_files) | set(prior_files)):
        a = today_files.get(rel)
        b = prior_files.get(rel)
        t_slugs = slugs_of(a) if a else set()
        p_slugs = slugs_of(b) if b else set()
        added = sorted(t_slugs - p_slugs)
        removed = sorted(p_slugs - t_slugs)
        if added or removed or not a or not b:
            rows.append(
                {
                    "file": str(rel).replace("\\", "/"),
                    "today_total": len(t_slugs),
                    "prior_total": len(p_slugs),
                    "added": added,
                    "removed": removed,
                    "missing_today": not a,
                    "missing_prior": not b,
                }
            )
    return rows


def write_report(today: str, prior_date: str | None, rows: list[dict]) -> Path:
    CHANGELOG_DIR.mkdir(parents=True, exist_ok=True)
    md_path = CHANGELOG_DIR / f"{today}.md"
    lines: list[str] = [f"# Snapshot diff — {today}", ""]
    if prior_date is None:
        lines.append("First snapshot — no prior to compare against.")
    else:
        lines.append(f"Compared against prior snapshot: **{prior_date}**")
    lines.append("")
    if not rows:
        lines.append("_No pass changes detected._")
    for r in rows:
        lines.append(f"## `{r['file']}`")
        if r["missing_today"]:
            lines.append("- **REMOVED ENTIRELY** (no longer scraped)")
        elif r["missing_prior"]:
            lines.append(f"- **NEW FILE** ({r['today_total']} passes)")
        else:
            lines.append(
                f"- today: {r['today_total']} passes, prior: {r['prior_total']} passes"
            )
        if r["added"]:
            lines.append("- Added: " + ", ".join(f"`{s}`" for s in r["added"]))
        if r["removed"]:
            lines.append("- Removed: " + ", ".join(f"`{s}`" for s in r["removed"]))
        lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return md_path


def main() -> int:
    if not list(index_files()):
        print(
            "No index files found — run scripts/scrape_static.py first.",
            file=sys.stderr,
        )
        return 2
    today = date.today().isoformat()
    today_dir = snapshot_today()
    prior_dir = latest_prior(today)
    rows = diff_index_files(today_dir, prior_dir) if prior_dir else []
    md_path = write_report(today, prior_dir.name if prior_dir else None, rows)
    print(f"Snapshot → {today_dir}", file=sys.stderr)
    print(f"Report   → {md_path}", file=sys.stderr)
    if rows:
        print(f"Changes detected in {len(rows)} index files.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
