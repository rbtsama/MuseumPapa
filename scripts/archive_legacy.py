"""一次性归档：把旧 sources 和旧 structured 移走，保留只读副本。"""
import shutil
from pathlib import Path
from datetime import date

ROOT = Path(__file__).resolve().parent.parent

def main():
    legacy_date = date.today().isoformat()
    src_legacy = ROOT / "src/malibbene/_legacy"
    src_legacy.mkdir(parents=True, exist_ok=True)
    sources_old = ROOT / "src/malibbene/sources"
    if sources_old.exists():
        target = src_legacy / "sources"
        if target.exists():
            raise SystemExit(f"already archived: {target}")
        shutil.move(str(sources_old), str(target))
        print(f"moved: src/malibbene/sources -> src/malibbene/_legacy/sources")

    data_legacy = ROOT / "data/_legacy" / legacy_date
    data_legacy.mkdir(parents=True, exist_ok=True)
    struct_old = ROOT / "data/structured"
    if struct_old.exists():
        for f in struct_old.iterdir():
            shutil.move(str(f), str(data_legacy / f.name))
        print(f"moved: data/structured/* -> data/_legacy/{legacy_date}/")

if __name__ == "__main__":
    main()
