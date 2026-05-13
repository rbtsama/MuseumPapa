"""Snapshot today's per-library index files and diff against the prior snapshot.

Covers all 3 scraping platforms via ``data/raw/<platform>/index/<lib_id>.json``:
  - assabet  (52 libs)
  - libcal   (5 libs including BPL)
  - museumkey (2 libs, catalog-only)

Reports two kinds of changes:
  1. **Structural** — passes added / removed in a library's catalog (BRD §6.1
     calls this out as a maintenance signal to catch new attractions).
  2. **Field-level** — same slug present in both snapshots but its
     ``pass_type``, ``label``, or ``benefits_text`` changed (ported from
     backup/diff_catalog.py).

Workflow:
  1. For each per-lib index file, copy it into
     ``data/snapshots/<YYYY-MM-DD>/<same relative path>``.
  2. Compare today's files against the latest prior snapshot (if any).
  3. Write a Markdown report to ``data/changelog/<YYYY-MM-DD>.md``.

Re-running on the same day is a no-op (today's snapshot dir already exists).
First run with no prior snapshot prints "first snapshot" and exits 0.
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

PLATFORMS = ("assabet", "libcal", "museumkey")


def index_files() -> list[Path]:
    out: list[Path] = []
    for platform in PLATFORMS:
        d = RAW_DIR / platform / "index"
        if d.exists():
            out.extend(sorted(d.glob("*.json")))
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


def passes_of(path: Path) -> dict[str, dict]:
    """Read a per-lib index file and return ``{slug: pass_record}`` (slug keys)."""
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    passes = data.get("passes")
    if not isinstance(passes, list):
        return {}
    out: dict[str, dict] = {}
    for p in passes:
        slug = p.get("slug") or p.get("pass_id")
        if slug:
            out[slug] = p
    return out


def _normspace(s: str) -> str:
    return " ".join((s or "").split()).strip().rstrip(".")


def diff_one_file(today_file: Path | None, prior_file: Path | None) -> dict:
    t = passes_of(today_file) if today_file else {}
    p = passes_of(prior_file) if prior_file else {}
    added = sorted(set(t) - set(p))
    removed = sorted(set(p) - set(t))
    field_changes: list[dict] = []
    for slug in sorted(set(t) & set(p)):
        a, b = t[slug], p[slug]
        if a.get("pass_type") != b.get("pass_type"):
            field_changes.append(
                {
                    "slug": slug,
                    "field": "pass_type",
                    "from": b.get("pass_type"),
                    "to": a.get("pass_type"),
                }
            )
        if a.get("label") != b.get("label"):
            field_changes.append(
                {
                    "slug": slug,
                    "field": "label",
                    "from": b.get("label"),
                    "to": a.get("label"),
                }
            )
        if _normspace(a.get("benefits_text", "")) != _normspace(b.get("benefits_text", "")):
            field_changes.append({"slug": slug, "field": "benefits_text"})
    return {
        "today_total": len(t),
        "prior_total": len(p),
        "added": added,
        "removed": removed,
        "field_changes": field_changes,
    }


def diff_index_files(today_dir: Path, prior_dir: Path) -> list[dict]:
    rows: list[dict] = []
    today_files = {p.relative_to(today_dir): p for p in today_dir.rglob("*.json")}
    prior_files = {p.relative_to(prior_dir): p for p in prior_dir.rglob("*.json")}
    for rel in sorted(set(today_files) | set(prior_files)):
        a = today_files.get(rel)
        b = prior_files.get(rel)
        d = diff_one_file(a, b)
        if d["added"] or d["removed"] or d["field_changes"] or not a or not b:
            rows.append(
                {
                    "file": str(rel).replace("\\", "/"),
                    "missing_today": not a,
                    "missing_prior": not b,
                    **d,
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
        lines.append("_No catalog changes detected._")
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
        for fc in r["field_changes"]:
            if fc["field"] == "benefits_text":
                lines.append(f"- ~ `{fc['slug']}`: benefits_text changed")
            else:
                lines.append(
                    f"- ~ `{fc['slug']}`: {fc['field']} {fc.get('from') or '∅'} → {fc.get('to') or '∅'}"
                )
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
        added = sum(len(r["added"]) for r in rows)
        removed = sum(len(r["removed"]) for r in rows)
        field = sum(len(r["field_changes"]) for r in rows)
        print(
            f"Changes: {added} added, {removed} removed, {field} field-level changes "
            f"across {len(rows)} index files.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
