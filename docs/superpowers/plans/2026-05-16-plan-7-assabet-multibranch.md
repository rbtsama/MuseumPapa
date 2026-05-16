# Plan-7: Assabet Multi-Branch Extension

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 plan-6 引入的 branch 模型,从 3 家 LibCal 多分馆 lib(BPL/Cambridge/Brookline)扩展到 Assabet 平台上同样有多个物理分馆的 lib(候选 8 家:Newton/Peabody/Medford/Lynn/Lawrence/Arlington/Somerville/Quincy)。

**Architecture:**
- **复用 plan-6 全套机制**:同一份 `config/branch_seeds.json` 增加候选 lib、同一个 `sources/branches/locations_page.py` 抓 HTML 快照、同一种 subagent extraction 流程、同一个 `build_branches.py` 合成 `branches.json`、同一个 `_classified.json` 喂给 `build/passes.py`。
- **新增的不确定性**:Assabet 平台的 pass detail 页**不分 branch**(`pass_type_raw` 只写 "picked up from the branch",不指明哪个)。所以本期对 Assabet 多分馆 lib 默认所有 branch 都持有该 pass,除非馆方网页另有说明。
- **第 0 个 task 是 reconnaissance**:**先用 1 个 subagent 走一遍 8 家候选 lib 的官网 + 已抓的 `data/raw/library_addresses/` HTML,确认到底有几家真的是多分馆**。如果某 lib 其实只有 1 个 patron-facing 物理点,直接踢出名单。**Reconnaissance 报告决定后续 task 5-8 的实际工作量**。
- 设计原则继续锚定 [[product-scope-query-only]] / [[audit-panel-must-serve-real-decision]] / [[feedback-no-api-call]]:branch 信息只为"用户开车去取卡"服务;审计页不加新面板,只让现有 multi-branch 子表自动多出几行;LLM 提取全走 subagent。

**Tech Stack:** Python 3.11+ + `malibbene.common.http` + `malibbene.common.geocode`(Nominatim);subagent dispatch(Sonnet);前端无改动(plan-6 已写好渲染规则,数据更新会自动生效)。

---

## File Structure

**New / modified files:**

- Modify: `config/branch_seeds.json` — 在 `multi_branch_libs` 数组追加确认为多分馆的 Assabet lib(每条 `{lib_id, locations_url, expected_branch_count}`)。
- Create: `data/raw/branches/<lib_id>.html` 每家新候选一份(由 `sources/branches/locations_page.py` 自动生成,**0 行代码改动**)。
- Create: `data/raw/branches/<lib_id>.json` 每家一份(subagent 写)。
- Create: `data/raw/branches/_pickup/<lib_id>/_classified.json`(简化版:对 Assabet 多分馆 lib,**默认每个 physical pass 都挂全部 branch**,因为 Assabet pass 页不分 branch;digital pass 照旧空数组)。这个 JSON 由一个**小脚本**生成,不需要 subagent。
- Create: `scripts/_tmp_assabet_recon.py` — 一次性 reconnaissance 脚本,产出 `_tmp_assabet_recon_report.md`(供你看完拍板要不要全做)。删掉。
- Create: `scripts/build_assabet_classifications.py` — 把 Assabet 多分馆 lib 的 `_classified.json` 一次性合成(逻辑见 Task 4)。
- 无前端改动。
- 无 audit 模板改动(plan-6 的 `_multi_branch_panel` 会自动多出 N 个 sub-table)。
- 测试:`tests/test_branch_schema.py` 自动扩展覆盖(无新增断言),`tests/test_build_branches.py`(plan-6 已写)同样自动适配。

**Out of scope(本期不做):**
- 抓 Assabet 后端拿"每个 branch 哪些 pass"的精细信号 — Assabet UI 没暴露,要登录账号才能看到 holds queue,违反 [[feedback-no-api-call]] 的"不调付费 / 登录态 API"精神。
- 中西部 MA / CW MARS / Minuteman 西郊扩展 — 那是地理扩展,不是 branch 模型扩展。
- 全 52 Assabet lib 都强行加 `_classified.json` — 单分馆的 lib 走 plan-6 已有的 `<lib_id>--main` 默认路径,不需要单独 classify。

---

## Task 0: Reconnaissance(必做 — 决定后续工作量)

**Files:**
- Create: `scripts/_tmp_assabet_recon.py`
- Create: `_tmp_assabet_recon_report.md`(repo 根目录)

- [ ] **Step 1: 写 recon 脚本(抓 8 家候选 lib 的 locations 页快照)**

```python
# scripts/_tmp_assabet_recon.py
"""One-shot: fetch likely locations pages for the 8 Assabet multi-branch
candidates so a subagent can confirm/reject each.

Delete this file once Task 0 closes.
"""
import sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from malibbene.common.http import fetch

CANDIDATES = {
    # lib_id: list of candidate locations-page URLs to try in order
    "newton":     ["https://www.newtonfreelibrary.net/locations/", "https://www.newtonfreelibrary.net/visit/", "https://www.newtonfreelibrary.net/"],
    "peabody":    ["https://www.peabodylibrary.org/locations/", "https://www.peabodylibrary.org/branches/", "https://www.peabodylibrary.org/"],
    "medford":    ["https://medfordlibrary.org/locations/", "https://medfordlibrary.org/visit/", "https://medfordlibrary.org/"],
    "lynn":       ["https://www.lynnpubliclibrary.org/locations/", "https://www.lynnpubliclibrary.org/branches/", "https://www.lynnpubliclibrary.org/"],
    "lawrence":   ["https://www.lawrencefreelibrary.org/locations/", "https://www.lawrencefreelibrary.org/"],
    "arlington":  ["https://www.robbinslibrary.org/locations/", "https://www.robbinslibrary.org/"],
    "somerville": ["https://www.somervillepubliclibrary.org/locations/", "https://www.somervillepubliclibrary.org/branches/", "https://www.somervillepubliclibrary.org/"],
    "quincy":     ["https://thomascranelibrary.org/locations/", "https://thomascranelibrary.org/branches/", "https://thomascranelibrary.org/"],
}

OUT = REPO / "data" / "raw" / "branches" / "_recon"
OUT.mkdir(parents=True, exist_ok=True)

for lib_id, urls in CANDIDATES.items():
    for url in urls:
        try:
            html = fetch(url)
        except Exception as e:
            print(f"FAIL {lib_id} {url}: {e}")
            continue
        if len(html) < 500:
            continue
        out = OUT / f"{lib_id}.html"
        out.write_text(html, encoding="utf-8")
        print(f"OK   {lib_id} {url} -> {len(html)} bytes")
        break
    else:
        print(f"SKIP {lib_id} — no candidate URL worked")
```

- [ ] **Step 2: 跑 recon**

Run: `python scripts/_tmp_assabet_recon.py`
Expected: 至少 6/8 行 OK。失败的人工补 URL(打开 `library_seeds.json` 找对应 `card_page` 的 domain,挨个试 `/locations`, `/visit`, `/about`)。

- [ ] **Step 3: 派一个 Sonnet subagent 一次性分类 8 家**

Controller 用 Agent tool 派(subagent_type=`general-purpose`,model=`sonnet`):

```
任务:对 8 家 Assabet 候选 lib 做 reconnaissance,判断每家是否真正多分馆。

INPUT:F:\pj\NorthShore Kids Events\data\raw\branches\_recon\*.html(8 个文件,
每个对应一家 lib 的官网入口页)

判断规则:
- "多分馆" = 有 >=2 个 patron-facing 物理服务点,每个有独立街道地址
- bookmobile / 流动馆 / 已永久关闭 / 单纯活动场地都不算
- 找不到明显的 "Locations" / "Branches" / "Hours & Locations" 链接 → 单分馆

OUTPUT:写一份 _tmp_assabet_recon_report.md 到 F:\pj\NorthShore Kids Events\
顶层目录,格式:

# Assabet Multi-Branch Reconnaissance

| lib_id | confirmed_multi | branch_count_est | locations_url | notes |
|---|---|---|---|---|
| newton     | yes/no  | N | <url> | <notes> |
| peabody    | yes/no  | N | <url> | <notes> |
| ...         | ...     | N | <url> | <notes> |

对于 confirmed_multi=yes 的行,locations_url 必须是"列出所有 branch 的页面"
(不一定是入口页,可能要点进去 — 你可以推断 URL 但要在 notes 里说"推断,需 fetch 验证")。

最后给一段总结:总共 K 家确认多分馆,平均每家 N 个 branch。
```

- [ ] **Step 4: 人工看报告 + 拍板**

Controller 把 `_tmp_assabet_recon_report.md` 内容打到对话里。**用户审阅后**告诉 controller 哪些 lib 进 Task 1-4,哪些剔除。

如果用户判定 0 家确认多分馆 — 整个 plan-7 直接 close,删掉 `scripts/_tmp_assabet_recon.py` + `data/raw/branches/_recon/` + 报告,commit "plan-7: closed — no Assabet lib confirmed as multi-branch"。

- [ ] **Step 5: Commit recon 产物(无论结果如何都要留痕)**

```bash
git -C "F:/pj/NorthShore Kids Events" add data/raw/branches/_recon/ _tmp_assabet_recon_report.md
git -C "F:/pj/NorthShore Kids Events" commit -m "plan-7: recon — N/8 Assabet libs confirmed multi-branch"
```

---

## Task 1: 扩展 branch_seeds.json + 复跑 locations 抓取

**Files:**
- Modify: `config/branch_seeds.json`
- Generate: `data/raw/branches/<lib_id>.html` 每家确认的多分馆 lib 一份

- [ ] **Step 1: 把 Task 0 确认的 lib 追加进 seed**

打开 `config/branch_seeds.json`,在 `multi_branch_libs` 数组**追加**(不要删 BPL/Cambridge/Brookline):

```json
{
  "lib_id": "newton",
  "locations_url": "<从 Task 0 报告 confirmed locations_url>",
  "expected_branch_count": <Task 0 报告 N>
}
```

每家一条。

- [ ] **Step 2: 跑现有 locations 抓取(不改任何代码)**

Run: `python scripts/scrape_branches.py`
Expected: 原有 3 家 + 新加 K 家共 (3+K) 行 status=ok。如果某新加 lib 失败,回 Task 0 拿正确 URL。

- [ ] **Step 3: Commit**

```bash
git -C "F:/pj/NorthShore Kids Events" add config/branch_seeds.json data/raw/branches/*.html
git -C "F:/pj/NorthShore Kids Events" commit -m "plan-7: snapshot locations pages for K Assabet multi-branch libs"
```

---

## Task 2: Subagent 抽 branch 列表

**Files:**
- Create: `data/raw/branches/<lib_id>.json` 每家新加 lib 一份(subagent 写)

- [ ] **Step 1: Controller 为每家新加 lib 派一个 Sonnet subagent(并发)**

模板(controller 用 Agent tool 派,subagent_type=`general-purpose`,model=`sonnet`):

```
任务:从 F:\pj\NorthShore Kids Events\data\raw\branches\<lib_id>.html 抽出
<lib_id> 的所有物理分馆,写成 JSON 到同目录 <lib_id>.json,格式严格如下:

{
  "lib_id": "<lib_id>",
  "source_url": "<从 branch_seeds.json>",
  "branches": [
    {
      "branch_id": "<lib_id>--<slug>",
      "name": "<branch name>",
      "address": {
        "street": "<street>",
        "city": "<city>",
        "state": "MA",
        "zip": "<5-digit zip or null>"
      },
      "hours_raw": "<hours block or null>",
      "extraction_notes": "<或 ''>"
    }
  ]
}

规则:
- slug = kebab-case from name(主馆 = `<lib_id>--main`)
- 只列 staffed patron-facing branches
- street 必须能在 HTML 里找到原文(不可 fabricate)
- zip 只在 HTML 明确出现时写,否则 null
- expected branch count(参考):<Task 0 报告里这家的 N>。差 1-2 个可接受,差更多在 extraction_notes 写明

写完用 Read 验证 JSON 合法,最后 stdout summary:
{"n": <count>, "samples": [{"id":"...","street":"..."}]}
```

- [ ] **Step 2: Controller 收集 + 抽样核对**

每家 lib 挑 2 个 branch 把 address 与 raw HTML 对照(防 fabrication)。

- [ ] **Step 3: Commit**

```bash
git -C "F:/pj/NorthShore Kids Events" add data/raw/branches/*.json
git -C "F:/pj/NorthShore Kids Events" commit -m "plan-7: subagent-extracted branch lists for K Assabet libs"
```

---

## Task 3: Geocode 新加 branch

**Files:**
- Modify: `data/raw/branches/<lib_id>.json` 就地追加 `geo`

- [ ] **Step 1: 写一次性脚本 `scripts/_tmp_geocode_assabet_branches.py`**

```python
"""One-shot: geocode every branch in data/raw/branches/<assabet_lib>.json
that doesn't already have geo. Reuses Nominatim cache so re-running is cheap.
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from malibbene.common.geocode import geocode

RAW = REPO / "data" / "raw" / "branches"

for f in sorted(RAW.glob("*.json")):
    if f.name.startswith("_"):
        continue
    data = json.loads(f.read_text(encoding="utf-8"))
    changed = False
    for b in data["branches"]:
        if b.get("geo"):
            continue
        addr = b["address"]
        q = f"{addr['street']}, {addr['city']}, {addr['state']} {addr.get('zip') or ''}".strip()
        res = geocode(q)
        if res.get("ok"):
            b["geo"] = {"lat": res["lat"], "lon": res["lon"]}
            changed = True
            print(f"OK  {b['branch_id']}")
        else:
            b["geo"] = None
            print(f"FAIL {b['branch_id']}  reason={res.get('error')}")
    if changed:
        f.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
```

- [ ] **Step 2: 跑(限速 1 req/s,新加 ~20-40 个 branch 大约 1 分钟)**

Run: `python scripts/_tmp_geocode_assabet_branches.py`
Expected: 绝大多数 OK。若有 `no_results`,直接编辑对应 raw JSON,从 Google Maps 拷 4 位小数坐标手填。≥95% 才放行。

- [ ] **Step 3: 删 tmp 脚本 + commit**

```bash
rm scripts/_tmp_geocode_assabet_branches.py
git -C "F:/pj/NorthShore Kids Events" add data/raw/branches/*.json
git -C "F:/pj/NorthShore Kids Events" commit -m "plan-7: geocode K Assabet libs' branches"
```

---

## Task 4: 合成 Assabet `_classified.json`(无 subagent,纯脚本)

**Files:**
- Create: `scripts/build_assabet_classifications.py`
- Generate: `data/raw/branches/_pickup/<lib_id>/_classified.json` 每家新加 lib 一份

**Why no subagent here:** Assabet pass 页只给 `pass_type_raw` 这种粒度的信息("digital" / "picked up from the branch" / "circulating"),**不分 branch**。所以分类逻辑是确定性的:digital pass → empty;physical → 全部 branch。一个 50 行脚本就够。

- [ ] **Step 1: 写脚本**

```python
# scripts/build_assabet_classifications.py
"""For Assabet multi-branch libs only: generate _classified.json by mapping
each pass to digital/physical based on the catalog's pass_type, and for
physical passes default to *all* branches of that lib (Assabet's pass detail
pages do not surface per-branch holdings).

Reads:
  data/raw/branches/<lib_id>.json   (must have geocoded branches)
  data/structured/library_catalog.json
Writes:
  data/raw/branches/_pickup/<lib_id>/_classified.json
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RAW = REPO / "data" / "raw" / "branches"
CAT = REPO / "data" / "structured" / "library_catalog.json"

# Inline list of multi-branch Assabet libs (filled from Task 0 outcome).
# Edit this list if the recon report changes scope.
ASSABET_MULTI = ["newton", "peabody", "medford", "lynn", "lawrence",
                 "arlington", "somerville", "quincy"]
# (Task 0 may shrink this list — replace with the confirmed subset before running.)

PHYSICAL_PASS_TYPES = {"physical-circ", "physical-coupon"}


def main() -> int:
    catalog = json.loads(CAT.read_text(encoding="utf-8"))["libraries"]
    for lib_id in ASSABET_MULTI:
        bpath = RAW / f"{lib_id}.json"
        if not bpath.exists():
            print(f"skip {lib_id}: no branches file")
            continue
        branches = json.loads(bpath.read_text(encoding="utf-8"))["branches"]
        branch_ids = [b["branch_id"] for b in branches if b.get("geo")]
        if not branch_ids:
            print(f"skip {lib_id}: no geocoded branches")
            continue

        lib_passes = catalog.get(lib_id, {}).get("passes", {})
        out_passes = []
        for slug, p in lib_passes.items():
            pass_type = p.get("pass_type", "unknown")
            if pass_type in PHYSICAL_PASS_TYPES:
                method = "physical_at_branch"
                pickups = list(branch_ids)
                evidence = f"assabet_pass_type={pass_type}; default_all_branches (Assabet UI does not expose per-branch holdings)"
            elif pass_type == "digital":
                method = "digital"
                pickups = []
                evidence = "assabet_pass_type=digital"
            else:
                method = "digital"
                pickups = []
                evidence = f"assabet_pass_type={pass_type}; defaulted_digital"
            out_passes.append({
                "pass_id": slug,
                "pickup_method": method,
                "pickup_branches": pickups,
                "evidence": evidence,
            })

        outdir = RAW / "_pickup" / lib_id
        outdir.mkdir(parents=True, exist_ok=True)
        (outdir / "_classified.json").write_text(
            json.dumps({"lib_id": lib_id, "passes": out_passes}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        n_phys = sum(1 for p in out_passes if p["pickup_method"] == "physical_at_branch")
        print(f"OK {lib_id}: {len(out_passes)} passes ({n_phys} physical) → {len(branch_ids)} branches each")

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: 跑**

Run: `python scripts/build_assabet_classifications.py`
Expected: K 行 OK。

- [ ] **Step 3: 让 build.py 读这些新 lib 的 classification**

打开 `scripts/build.py`,定位 plan-6 加的这段:

```python
for lib in ("bpl", "cambridge", "brookline"):
    cf = raw_root / "branches" / "_pickup" / lib / "_classified.json"
    if cf.exists():
        data = json.loads(cf.read_text(encoding="utf-8"))
        classifications[lib] = {p["pass_id"]: p for p in data.get("passes", [])}
```

改成自动扫描所有存在的 `_classified.json`:

```python
for cf in (raw_root / "branches" / "_pickup").glob("*/_classified.json"):
    lib = cf.parent.name
    data = json.loads(cf.read_text(encoding="utf-8"))
    classifications[lib] = {p["pass_id"]: p for p in data.get("passes", [])}
```

- [ ] **Step 4: 跑完整 build + 验收**

Run:
```
python scripts/build.py
python -m pytest tests/test_branch_schema.py tests/test_build_branches.py -v
```
Expected:
- build 显示 `n_branches` 从 92 涨到 (92 + 新增数)
- `n_physical_at_branch` 上升(新加 K 家 lib 的 physical pass × branch fan-out)
- 5 个测试全 PASS

- [ ] **Step 5: Commit**

```bash
git -C "F:/pj/NorthShore Kids Events" add scripts/build_assabet_classifications.py scripts/build.py data/raw/branches/_pickup/ data/structured/branches.json data/structured/passes.json data/structured/library_catalog.json
git -C "F:/pj/NorthShore Kids Events" commit -m "plan-7: classify Assabet multi-branch lib passes (default all-branches for physical)"
```

---

## Task 5: Audit 页面 + 前端验收(无代码改动)

**Files:**
- 无修改,只重跑生成

- [ ] **Step 1: 重生成 audit 页**

Run: `python scripts/build_audit_site.py`
Expected: `libraries.html` 底部"多分馆 lib · Branch breakdown"section 现在有 (3 + K) 张 sub-table。

- [ ] **Step 2: 验证 sub-table 行数 vs Task 0 report**

```bash
python -c "
from pathlib import Path
import re
html = Path('audit/libraries.html').read_text(encoding='utf-8')
for lib in ['bpl', 'cambridge', 'brookline', 'newton', 'peabody']:  # 列你确认的
    n = len(re.findall(rf'class=\"mono\">{lib}--', html))
    print(f'{lib}: {n} rows')
"
```

数字应该匹配 `data/raw/branches/<lib>.json` 的 branch 数。

- [ ] **Step 3: 前端构建 + 单元测试**

```bash
cd web
pnpm run build
pnpm test
```
Expected: build 0 error,所有测试 PASS。Plan-6 已实现按 branch 渲染规则,数据自动接上。

- [ ] **Step 4: Commit audit 重生成**

```bash
git -C "F:/pj/NorthShore Kids Events" add audit/libraries.html
git -C "F:/pj/NorthShore Kids Events" commit -m "plan-7: regenerate audit page with extended multi-branch coverage"
```

---

## Self-Review Notes

- ✅ **Spec 覆盖**:plan-6 self-review 留口子的"Assabet 多分馆"工作项全部对应 task。
- ✅ **占位符扫描**:无 TBD / "适当处理"等。Task 0 步骤 4 的"用户判定"是有明确意义的 checkpoint(不是占位符)。
- ✅ **类型一致**:`pickup_method` / `pickup_branches` / `branch_id` 命名与 plan-6 完全一致;`_classified.json` 结构沿用 plan-6 schema(`{lib_id, passes:[{pass_id, pickup_method, pickup_branches, evidence}]}`)。
- ✅ **TDD/YAGNI**:不写新单元测试 — plan-6 的 `test_branch_schema.py` + `test_build_branches.py` 已是 schema-lock,新 lib 加入自动覆盖。不引入新组件、新 frontend 类型、新 audit panel。
- ✅ **DRY**:90% 工作量复用 plan-6 已写的 module(`branches/locations_page.py`, `build_branches.py`, build pipeline, audit `_multi_branch_panel`, frontend `getBranchesForPass`)。
- ✅ **风险标注**:Task 0 是 hard gate — 如果 reconnaissance 结果显示 0 家确认多分馆,plan 直接 close;若只确认 1-2 家,后续 task 5 分钟扫完。Task 4 用脚本而非 subagent 是因为 Assabet pass 信号不分 branch,subagent 跑不出更精细的结果。

---

**已存盘:`docs/superpowers/plans/2026-05-16-plan-7-assabet-multibranch.md`。等你审完批改 / 拍板要不要 Task 0 先跑 reconnaissance 再决定后续工作量。**
