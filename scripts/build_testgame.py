"""构建 testgame.html：读 data/structured/* -> 抽样 -> 渲染 -> 写根目录。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from malibbene.testgame.select import select_sample  # noqa: E402
from malibbene.testgame.render import render_html  # noqa: E402

STRUCT = REPO / "data" / "structured"
PKG = REPO / "src" / "malibbene" / "testgame"


def main() -> None:
    libs = json.loads((STRUCT / "libraries.json").read_text(encoding="utf-8"))["libraries"]
    attrs = json.loads((STRUCT / "attractions.json").read_text(encoding="utf-8"))["attractions"]
    passes = json.loads((STRUCT / "passes.json").read_text(encoding="utf-8"))["passes"]

    sample = select_sample(libs, attrs, passes)
    template = (PKG / "template.html").read_text(encoding="utf-8")
    logic = (PKG / "logic.mjs").read_text(encoding="utf-8")
    html = render_html(sample, logic, template)

    out = REPO / "testgame.html"
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out} ({len(html)} bytes); "
          f"libs={len(sample['libraries'])} attractions={len(sample['attractions'])} passes={len(sample['passes'])}")


if __name__ == "__main__":
    main()
