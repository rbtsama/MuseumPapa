"""Run all build/*.py, write data/structured/*, print validate report."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from malibbene.build.libraries import build_libraries
from malibbene.build.attractions import build_attractions
from malibbene.build.branches import build_branches
from malibbene.build.passes import build_passes
from malibbene.build.validate import validate_build, check_build_consistency


def main():
    raw = ROOT/"data/raw"; over = ROOT/"data/overrides"; out = ROOT/"data/structured"
    out.mkdir(parents=True, exist_ok=True)
    build_libraries(seed_path=ROOT/"config/library_seeds.json",
                    raw_root=raw, overrides_root=over, out_path=out/"libraries.json")
    build_attractions(raw_root=raw, overrides_root=over, out_path=out/"attractions.json")
    build_branches(raw_root=raw, overrides_root=over, out_path=out/"branches.json",
                   libraries_path=out/"libraries.json")
    build_passes(raw_root=raw, overrides_root=over, out_path=out/"passes.json")
    check_build_consistency(out)
    report = validate_build(libraries=out/"libraries.json",
                             attractions=out/"attractions.json",
                             passes_file=out/"passes.json")
    print("=== Validate Report ===")
    import json; print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
