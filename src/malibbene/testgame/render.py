"""把抽样数据 + 决策逻辑注入模板，产出自包含 HTML。"""
from __future__ import annotations

import json


def _strip_exports(logic_js: str) -> str:
    # logic.mjs 用 `export function ...`；classic <script> 内联需去掉 export 关键字
    return logic_js.replace("export function", "function").replace("export default", "")


def render_html(sample: dict, logic_js: str, template: str) -> str:
    data_js = "const TESTGAME_DATA = " + json.dumps(sample, ensure_ascii=False, indent=2) + ";"
    logic_inline = _strip_exports(logic_js)
    if "export function" in logic_inline or "export default" in logic_inline:
        raise ValueError("内联逻辑仍残留 ESM export，会导致 <script> 解析失败")
    html = template.replace("/*__LOGIC__*/", logic_inline).replace("/*__DATA__*/", data_js)
    if "/*__LOGIC__*/" in html or "/*__DATA__*/" in html:
        raise ValueError("模板注入点未全部替换")
    return html
