"""Run the deterministic coupon extractor against all pending requests.

Usage:
    python scripts/extract_coupons.py [--force] [--platform assabet|libcal|all]
                                      [--out-dir data/raw]

Reads data/raw/<platform>/_pending/coupons/<lib>__<slug>.json and writes
data/raw/<platform>/coupons/<lib>__<slug>.json. Idempotent: skips existing
outputs with status=ok unless --force is passed; re-processes status=failed
files when the underlying benefit_text has changed.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from malibbene.sources_v2.coupons.extract import extract_coupon  # noqa: E402


def _process_platform(platform: str, raw_root: Path, *, force: bool) -> dict[str, int]:
    pending_dir = raw_root / platform / "_pending" / "coupons"
    out_dir = raw_root / platform / "coupons"
    out_dir.mkdir(parents=True, exist_ok=True)

    counts = {"total": 0, "written": 0, "skipped": 0, "failed": 0, "errors": 0}
    if not pending_dir.exists():
        return counts

    for src in sorted(pending_dir.glob("*.json")):
        counts["total"] += 1
        try:
            req = json.loads(src.read_text(encoding="utf-8"))
        except Exception as e:  # pragma: no cover - defensive
            print(f"  ! cannot read {src}: {e}", file=sys.stderr)
            counts["errors"] += 1
            continue

        out = out_dir / src.name
        if out.exists() and not force:
            try:
                prev = json.loads(out.read_text(encoding="utf-8"))
                if prev.get("status") == "ok":
                    counts["skipped"] += 1
                    continue
            except Exception:
                pass

        result = extract_coupon(
            library_id=req.get("library_id", ""),
            attraction_slug=req.get("attraction_slug", ""),
            benefit_text=req.get("benefit_text", ""),
            source_phrases=req.get("source_phrases") or [],
            platform=req.get("platform", platform),
        )
        if result["status"] == "ok":
            counts["written"] += 1
        else:
            counts["failed"] += 1
        out.write_text(
            json.dumps(result, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    return counts


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--platform",
        default="all",
        choices=["all", "assabet", "libcal", "museumkey"],
    )
    ap.add_argument("--out-dir", default=str(ROOT / "data" / "raw"))
    ap.add_argument("--force", action="store_true",
                    help="Overwrite existing outputs even if status=ok.")
    args = ap.parse_args()

    raw_root = Path(args.out_dir)
    platforms = (
        ["assabet", "libcal", "museumkey"]
        if args.platform == "all"
        else [args.platform]
    )
    grand = {"total": 0, "written": 0, "skipped": 0, "failed": 0, "errors": 0}
    for p in platforms:
        print(f"[{p}] extracting coupons")
        counts = _process_platform(p, raw_root, force=args.force)
        for k, v in counts.items():
            grand[k] += v
        print(f"  total={counts['total']} written={counts['written']} "
              f"skipped={counts['skipped']} failed={counts['failed']} "
              f"errors={counts['errors']}")
    print(f"[done] {grand}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
