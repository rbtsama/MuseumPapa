"""Run all build/*.py, write data/structured/*, print validate report."""
from pathlib import Path
from malibbene.build.libraries import build_libraries
from malibbene.build.attractions import build_attractions
from malibbene.build.branches import build_branches
from malibbene.build.passes import build_passes
from malibbene.build.validate import validate_build

ROOT = Path(__file__).resolve().parent.parent

def main():
    raw = ROOT/"data/raw"; over = ROOT/"data/overrides"; out = ROOT/"data/structured"
    out.mkdir(parents=True, exist_ok=True)
    build_libraries(seed_path=ROOT/"config/library_seeds.json",
                    raw_root=raw, overrides_root=over, out_path=out/"libraries.json")
    build_attractions(raw_root=raw, overrides_root=over, out_path=out/"attractions.json")
    build_branches(raw_root=raw, overrides_root=over, out_path=out/"branches.json")
    build_passes(raw_root=raw, overrides_root=over, out_path=out/"passes.json")
    report = validate_build(libraries=out/"libraries.json",
                             attractions=out/"attractions.json",
                             passes_file=out/"passes.json")
    print("=== Validate Report ===")
    import json; print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
