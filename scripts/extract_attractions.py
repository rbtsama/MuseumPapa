"""Run the four deterministic attraction-page extractors.

Reads pending requests from data/raw/attractions/_pending/<kind>/<slug>.json
and writes results to data/raw/attractions/<kind>/<slug>.json. Idempotent:
skips existing outputs with status=ok unless --force.

Kinds: visitor_eligibility, reservation, prices, hours.

Usage:
    python scripts/extract_attractions.py --kind all
    python scripts/extract_attractions.py --kind prices --force
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

from malibbene.sources_v2.attractions.extract_visitor_eligibility import (  # noqa: E402
    extract_visitor_eligibility,
)
from malibbene.sources_v2.attractions.extract_reservation import (  # noqa: E402
    extract_reservation,
)
from malibbene.sources_v2.attractions.extract_prices import extract_prices  # noqa: E402
from malibbene.sources_v2.attractions.extract_hours import extract_hours  # noqa: E402

_EXTRACTORS = {
    "visitor_eligibility": extract_visitor_eligibility,
    "reservation": extract_reservation,
    "prices": extract_prices,
    "hours": extract_hours,
}


def _process_kind(kind: str, raw_root: Path, *, force: bool) -> dict[str, int]:
    pending_dir = raw_root / "attractions" / "_pending" / kind
    out_dir = raw_root / "attractions" / kind
    out_dir.mkdir(parents=True, exist_ok=True)
    fn = _EXTRACTORS[kind]
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

        slug = req.get("slug") or src.stem
        out = out_dir / f"{slug}.json"
        if out.exists() and not force:
            try:
                prev = json.loads(out.read_text(encoding="utf-8"))
                if prev.get("status") == "ok":
                    counts["skipped"] += 1
                    continue
            except Exception:
                pass
        try:
            result = fn(slug, raw_root)
        except Exception as e:  # pragma: no cover - defensive
            counts["errors"] += 1
            print(f"  ! {kind}/{slug}: {e}", file=sys.stderr)
            continue
        if result.get("status") == "ok":
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
        "--kind", default="all",
        choices=["all", "visitor_eligibility", "reservation", "prices", "hours"],
    )
    ap.add_argument("--out-dir", default=str(ROOT / "data" / "raw"))
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    raw_root = Path(args.out_dir)
    kinds = list(_EXTRACTORS) if args.kind == "all" else [args.kind]
    grand = {"total": 0, "written": 0, "skipped": 0, "failed": 0, "errors": 0}
    for k in kinds:
        print(f"[{k}]")
        c = _process_kind(k, raw_root, force=args.force)
        for kk, vv in c.items():
            grand[kk] += vv
        print(f"  total={c['total']} written={c['written']} skipped={c['skipped']} "
              f"failed={c['failed']} errors={c['errors']}")
    print(f"[done] {grand}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
