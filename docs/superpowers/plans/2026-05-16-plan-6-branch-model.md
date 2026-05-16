# Plan-6: Branch-Level Pickup Model (lib_id → branch)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `lib_id` 降级为"发券组织"内部 ID,新增 branch 层数据模型,让实体券(physical pass)能告诉用户**具体去哪个物理分馆取**;前端按 `pickup_method` 区分电子券 / 实体券两套展示。

**Architecture:**
- Schema 升级:`passes.json` 每条记录新增 `pickup_method` ∈ {`digital`, `physical_at_branch`},实体券附 `pickup_branches[]`(branch_id 引用)。新建 `data/structured/branches.json` 存所有 branch 的 `name/address/geo/parent_lib_id`。
- Scraping:**只重抓 BPL(26)、Cambridge(7)、Brookline(3)** 三家多分馆 LibCal 馆;其余 56 个 lib_id 视为"单分馆"(pickup_branches 自动等于该 lib 的主地址)。
- 设计原则对齐 [[product-scope-query-only]]、[[audit-panel-must-serve-real-decision]]、[[feedback-no-api-call]]:branch 数据必须服务用户"开车去哪取卡"的决策,不引入新的组织抽象;LLM 提取通过 subagent dispatch,不调 Anthropic API。

**Tech Stack:** Python 3.11+,`urllib`(via `malibbene.common.http`),`malibbene.common.geocode`(OSM Nominatim),subagent dispatch(Sonnet 做提取)。前端 React + HeroUI(plan-3/4 已搭好)。

---

## File Structure

**New / modified files:**

- Create: `config/branch_seeds.json` — BPL/Cambridge/Brookline 三家 locations 页 URL + manual override 的 branch 列表种子。
- Create: `data/raw/branches/<lib_id>.html` — locations 页快照(只对三家多分馆 lib)。
- Create: `data/raw/branches/<lib_id>.json` — subagent 抽出的 branch 列表 raw。
- Create: `data/raw/branches/_pickup/<lib_id>/<pass_id>.json` — subagent 抽出的 per-pass pickup_branches raw。
- Create: `data/structured/branches.json` — 最终 branch metadata(name/address/geo/parent_lib_id)。
- Modify: `data/structured/passes.json`(schema 新增 `pickup_method` + `pickup_branches[]`)— 通过 build 重新生成。
- Modify: `data/structured/library_catalog.json` — pass 节点附 `pickup_method` + `pickup_branches[]` raw。
- Create: `src/malibbene/sources/branches/__init__.py`
- Create: `src/malibbene/sources/branches/locations_page.py` — 抓三家 LibCal 馆的 locations 列表页(快照式)。
- Create: `src/malibbene/sources/branches/pickup_hints.py` — 重抓 BPL/Cambridge/Brookline 的 pass detail 页,把 "Available at <branch>" 之类文本切片落盘给 subagent。
- Create: `scripts/scrape_branches.py` — CLI 入口,串起 locations + pickup_hints。
- Create: `scripts/build_branches.py` — 把 raw + subagent JSON 整合成 `branches.json`,并 backfill 单分馆 lib。
- Modify: `scripts/build.py` — 调用 build_branches、把 pickup_method/pickup_branches 写到 passes.json。
- Modify: `audit/libraries.html` 生成器(`scripts/build_audit.py` 或同名,见现有结构)— 多分馆 lib 展开 branch 子行。
- Modify: `web/src/components/PassCard.tsx`(或类似)— 按 pickup_method 切换展示。
- Test: `tests/test_branch_schema.py`、`tests/test_build_branches.py`、`tests/test_pickup_method_classifier.py`。

**Out of scope(本期不做):**
- Assabet / MuseumKey 多分馆拆分(数据源里 Assabet 一馆通常本身就是单点;若发现 Assabet 多分馆,记 GitHub issue,plan-7 处理)。
- "branch 之间可借还" / "branch 之间网络归属差异" 这类组织抽象 — 违反 [[audit-panel-must-serve-real-decision]]。
- 实体券的预约取/还时间窗 — 留给 availability 拓展。

---

## Task 1: Schema 升级 + 单元测试锁定字段

**Files:**
- Create: `tests/test_branch_schema.py`
- Modify: `docs/BRD.md`(§6.1 增加 pickup_method / pickup_branches 字段说明)

- [ ] **Step 1: 写 schema 锁定测试(失败)**

```python
# tests/test_branch_schema.py
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_passes_have_pickup_method():
    data = json.loads((ROOT / "data/structured/passes.json").read_text(encoding="utf-8"))
    for p in data["passes"]:
        assert p.get("pickup_method") in {"digital", "physical_at_branch"}, \
            f"{p['library_id']}/{p['attraction_slug']} missing pickup_method"
        if p["pickup_method"] == "physical_at_branch":
            assert isinstance(p.get("pickup_branches"), list) and len(p["pickup_branches"]) >= 1, \
                f"{p['library_id']}/{p['attraction_slug']} physical pass needs >=1 pickup_branches"

def test_branches_json_shape():
    data = json.loads((ROOT / "data/structured/branches.json").read_text(encoding="utf-8"))
    seen_ids = set()
    for b in data["branches"]:
        assert b["id"] not in seen_ids, f"duplicate branch id {b['id']}"
        seen_ids.add(b["id"])
        for k in ("id", "name", "parent_lib_id", "address", "geo"):
            assert k in b, f"branch {b.get('id')} missing {k}"
        assert b["address"].get("street")
        assert b["geo"].get("lat") and b["geo"].get("lon")

def test_pickup_branch_ids_resolve():
    branches = json.loads((ROOT / "data/structured/branches.json").read_text(encoding="utf-8"))
    valid = {b["id"] for b in branches["branches"]}
    passes = json.loads((ROOT / "data/structured/passes.json").read_text(encoding="utf-8"))
    for p in passes["passes"]:
        if p["pickup_method"] != "physical_at_branch":
            continue
        for bid in p["pickup_branches"]:
            assert bid in valid, f"{p['library_id']}/{p['attraction_slug']} → unknown branch {bid}"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/test_branch_schema.py -v`
Expected: 3 个 FAIL(KeyError / missing pickup_method)。

- [ ] **Step 3: 更新 BRD.md §6.1 加上字段定义**

在 BRD `passes.json` 部分追加:

```markdown
### `pickup_method` (string, required)
- `digital`:电子券,用户拿到 URL/PDF 即可,无需到馆。**前端不展示 lib_id**(只显示发券组织的"售出方"信息用于审计跟踪)。
- `physical_at_branch`:实体券/卡,必须到具体物理分馆领取。**前端必须展示 pickup_branches 的物理地址。**

### `pickup_branches` (array<branch_id>, required when pickup_method=physical_at_branch)
引用 `branches.json` 的 branch ID。一个 pass 可同时挂多个 branch(BPL 多分馆共享一种 pass);单分馆 lib 该数组只有一个元素 = `<lib_id>--main`。
```

新建 `branches.json` 章节说明(name/parent_lib_id/address/geo)。

- [ ] **Step 4: Commit**

```bash
rtk git add tests/test_branch_schema.py docs/BRD.md
rtk git commit -m "plan-6: schema-lock tests + BRD entries for pickup_method / branches"
```

---

## Task 2: Branch seed 配置 + locations 页抓取

**Files:**
- Create: `config/branch_seeds.json`
- Create: `src/malibbene/sources/branches/__init__.py`(空文件)
- Create: `src/malibbene/sources/branches/locations_page.py`
- Create: `scripts/scrape_branches.py`

- [ ] **Step 1: 写 seed**

```json
// config/branch_seeds.json
{
  "_comment": "BPL/Cambridge/Brookline 三家多分馆 LibCal 馆的 locations 入口页。其余 56 lib 视为单分馆,在 build_branches 阶段自动合成 <lib_id>--main。",
  "multi_branch_libs": [
    {
      "lib_id": "bpl",
      "locations_url": "https://www.bpl.org/locations/",
      "expected_branch_count": 26
    },
    {
      "lib_id": "cambridge",
      "locations_url": "https://www.cambridgema.gov/cpl/aboutthelibrary/libraries",
      "expected_branch_count": 7
    },
    {
      "lib_id": "brookline",
      "locations_url": "https://www.brooklinelibrary.org/locations/",
      "expected_branch_count": 3
    }
  ]
}
```

- [ ] **Step 2: 写 locations_page.py(快照式 fetch + 落盘 HTML,不做抽取)**

```python
# src/malibbene/sources/branches/locations_page.py
"""Snapshot multi-branch library locations pages to data/raw/branches/.

Extraction (parse branch list → name/address/hours) is intentionally NOT done
here — that's a subagent task. This module only fetches HTML reliably so the
subagent has a deterministic input. See [[feedback-no-api-call]] for why we
don't call any LLM API from Python.
"""
from __future__ import annotations
import json
from pathlib import Path
from malibbene.common.http import fetch

REPO_ROOT = Path(__file__).resolve().parents[4]
SEEDS_PATH = REPO_ROOT / "config" / "branch_seeds.json"
OUT_DIR = REPO_ROOT / "data" / "raw" / "branches"

def fetch_all() -> list[dict]:
    seeds = json.loads(SEEDS_PATH.read_text(encoding="utf-8"))["multi_branch_libs"]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    for entry in seeds:
        lib_id = entry["lib_id"]
        url = entry["locations_url"]
        try:
            html = fetch(url)
        except Exception as e:
            results.append({"lib_id": lib_id, "status": f"failed:{e}"})
            continue
        out = OUT_DIR / f"{lib_id}.html"
        out.write_text(html, encoding="utf-8")
        results.append({"lib_id": lib_id, "status": "ok", "bytes": len(html), "url": url})
    return results
```

- [ ] **Step 3: 写 CLI**

```python
# scripts/scrape_branches.py
"""Snapshot locations pages for multi-branch libs (BPL/Cambridge/Brookline)."""
from malibbene.sources.branches.locations_page import fetch_all

if __name__ == "__main__":
    for r in fetch_all():
        print(r)
```

- [ ] **Step 4: 实跑验收**

Run: `python scripts/scrape_branches.py`
Expected: 3 行 status=ok,字节数 > 5000。然后 `ls data/raw/branches/*.html` 应见 3 个文件。

- [ ] **Step 5: Commit**

```bash
rtk git add config/branch_seeds.json src/malibbene/sources/branches/ scripts/scrape_branches.py
rtk git commit -m "plan-6: snapshot locations pages for BPL/Cambridge/Brookline"
```

---

## Task 3: Subagent 抽取 branch 列表 → raw JSON

**Files:**
- Create: `data/raw/branches/<lib_id>.json`(由 subagent 写)

- [ ] **Step 1: Controller 派 3 个 Sonnet subagent(并发)**

每个 subagent 任务模板(controller 用 Agent tool 派,subagent_type=`general-purpose`,model=`sonnet`):

```
任务:读 F:\pj\NorthShore Kids Events\data\raw\branches\<lib_id>.html,
抽出所有物理分馆,写到同目录 <lib_id>.json,格式:

{
  "lib_id": "<lib_id>",
  "source_url": "<URL from branch_seeds.json>",
  "branches": [
    {
      "branch_id": "<lib_id>--<slug>",   // 例如 bpl--copley, bpl--east-boston
      "name": "<原页 branch name>",
      "address": {
        "street": "<...>",
        "city": "<...>",
        "state": "MA",
        "zip": "<5-digit>"
      },
      "hours_raw": "<原文 hours block 或 null>",
      "extraction_notes": "<本馆若有合并 / 关闭 / 已迁址,简短记下>"
    }
  ]
}

规则:
- slug 必须 kebab-case,字母数字 + 短横线,无重音符号
- 找不到完整 zip 就留 null,但 street/city 必须有
- 不要凭印象补 BPL 的 Bookmobile 等非取卡点 — 只列 staffed 分馆
- 写完后用 Read 确认 JSON 合法
```

- [ ] **Step 2: 控制器收集 + 抽样检查**

Controller 读三个 JSON 文件,打印 `len(branches)`。BPL 期望 ≥24(总馆+主要分馆,允许差 1-2,Bookmobile/East Boston Brewer-Burroughs 等取舍记 extraction_notes);Cambridge 期望 7;Brookline 期望 3。

抽样规则:每馆挑 2 个 branch,把 address 与 raw HTML 对照一次,确认不是 fabrication([[audit-panel-must-serve-real-decision]] 数据正确性原则)。

- [ ] **Step 3: Commit**

```bash
rtk git add data/raw/branches/bpl.json data/raw/branches/cambridge.json data/raw/branches/brookline.json
rtk git commit -m "plan-6: subagent-extracted branch lists (BPL/Cambridge/Brookline)"
```

---

## Task 4: Branch 地理编码

**Files:**
- Modify: `data/raw/branches/<lib_id>.json`(就地追加 geo)

- [ ] **Step 1: 写一次性脚本 `scripts/_tmp_geocode_branches.py`**

```python
import json
from pathlib import Path
from malibbene.common.geocode import geocode

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/branches"

for f in RAW.glob("*.json"):
    data = json.loads(f.read_text(encoding="utf-8"))
    changed = False
    for b in data["branches"]:
        if b.get("geo"):
            continue
        addr = b["address"]
        q = f"{addr['street']}, {addr['city']}, {addr['state']} {addr.get('zip','')}".strip()
        try:
            res = geocode(q)
        except Exception as e:
            print(f"network fail {b['branch_id']}: {e}"); continue
        if res:
            b["geo"] = {"lat": res["lat"], "lon": res["lon"]}
            changed = True
            print(f"OK {b['branch_id']}")
        else:
            b["geo"] = None
            print(f"no_results {b['branch_id']}")
    if changed:
        f.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
```

- [ ] **Step 2: 实跑(注意 1 req/sec 限流,本期 ~36 次,约 1 分钟)**

Run: `python scripts/_tmp_geocode_branches.py`
Expected:绝大多数 OK;手工补 `null` 的 branch(直接编辑 raw JSON,从 Google Maps 拷坐标到 4 位小数)。≥ 95% branch 有 geo 才放行。

- [ ] **Step 3: 删 `_tmp_` 脚本并 commit**

```bash
rm scripts/_tmp_geocode_branches.py
rtk git add data/raw/branches/*.json
rtk git commit -m "plan-6: geocode branch addresses via Nominatim"
```

---

## Task 5: 重抓 pass detail 页 → 提取 pickup_method + pickup_branches 提示

**Files:**
- Create: `src/malibbene/sources/branches/pickup_hints.py`
- Create: `data/raw/branches/_pickup/<lib_id>/<pass_id>.txt`(剪裁后的文本块)
- Modify: `scripts/scrape_branches.py`(加 `--pickup` 子模式)

- [ ] **Step 1: 写 pickup_hints.py(reuse `data/raw/libcal/index/<lib_id>.json` 已有的 pass URL 列表)**

```python
# src/malibbene/sources/branches/pickup_hints.py
"""For BPL/Cambridge/Brookline only: re-fetch each pass detail page and slice
out the body section that mentions branches / pickup, save to a flat text file
the subagent can read without HTML noise.
"""
from __future__ import annotations
import json, re
from pathlib import Path
from malibbene.common.http import fetch

REPO_ROOT = Path(__file__).resolve().parents[4]
INDEX_DIR = REPO_ROOT / "data/raw/libcal/index"
OUT_ROOT = REPO_ROOT / "data/raw/branches/_pickup"
TARGET_LIBS = {"bpl", "cambridge", "brookline"}

BODY_RE = re.compile(r'<div[^>]*id="s-lc-pass-desc"[^>]*>(.*?)</div>', re.DOTALL | re.IGNORECASE)
TAG_RE = re.compile(r"<[^>]+>")

def harvest():
    out = []
    for lib_id in TARGET_LIBS:
        idx_path = INDEX_DIR / f"{lib_id}.json"
        if not idx_path.exists():
            out.append({"lib_id": lib_id, "status": "missing_index"}); continue
        data = json.loads(idx_path.read_text(encoding="utf-8"))
        lib_out = OUT_ROOT / lib_id
        lib_out.mkdir(parents=True, exist_ok=True)
        for p in data.get("passes", []):
            url = p.get("source_url")
            if not url: continue
            pass_id = p.get("source_pass_id") or p.get("benefit_id")
            try:
                html = fetch(url)
            except Exception as e:
                out.append({"lib_id": lib_id, "pass": pass_id, "status": f"failed:{e}"}); continue
            m = BODY_RE.search(html)
            text = TAG_RE.sub(" ", m.group(1) if m else html)
            text = re.sub(r"\s+", " ", text).strip()
            (lib_out / f"{pass_id}.txt").write_text(text, encoding="utf-8")
            out.append({"lib_id": lib_id, "pass": pass_id, "status": "ok", "chars": len(text)})
    return out
```

- [ ] **Step 2: CLI 串起**

Edit `scripts/scrape_branches.py`:

```python
"""Snapshot locations pages (default) or harvest pass-pickup hints (--pickup)."""
import sys
from malibbene.sources.branches.locations_page import fetch_all
from malibbene.sources.branches.pickup_hints import harvest

if __name__ == "__main__":
    if "--pickup" in sys.argv:
        for r in harvest(): print(r)
    else:
        for r in fetch_all(): print(r)
```

- [ ] **Step 3: 实跑**

Run: `python scripts/scrape_branches.py --pickup`
Expected: BPL ~45 行 ok、Cambridge ~30、Brookline ~20。`ls data/raw/branches/_pickup/bpl | wc -l` ≥ 40。

- [ ] **Step 4: Commit**

```bash
rtk git add src/malibbene/sources/branches/pickup_hints.py scripts/scrape_branches.py
rtk git add data/raw/branches/_pickup/
rtk git commit -m "plan-6: harvest pass-pickup hint text for 3 multi-branch libs"
```

---

## Task 6: Subagent 分类 pickup_method + 列 pickup_branches

**Files:**
- Create: `data/raw/branches/_pickup/<lib_id>/_classified.json`(subagent 产物,一个 lib 一个文件)

- [ ] **Step 1: Controller 派 3 个 Sonnet subagent(并发)**

任务模板:

```
任务:读 F:\pj\NorthShore Kids Events\data\raw\branches\_pickup\<lib_id>\*.txt
(每个文件是一个 pass 的描述纯文本)和同目录上一级 ../<lib_id>.json 的 branches
列表,产出 _classified.json:

{
  "lib_id": "<lib_id>",
  "passes": [
    {
      "pass_id": "<filename without .txt>",
      "pickup_method": "digital" | "physical_at_branch",
      "pickup_branches": ["<branch_id>", ...],   // 仅 physical_at_branch 必填
      "evidence": "<原文 1-2 句话,锚定判断依据>"
    }
  ]
}

分类规则(严格按文本判断,不要凭印象):
- 文本含 "digital" / "print at home" / "emailed link" / "online pass" / "e-pass"
  → pickup_method=digital, pickup_branches=[]
- 文本含 "pick up at" / "available at <branch>" / "loan" / "physical pass" / "borrow at"
  → physical_at_branch
- 都没明示就归 digital(BPL/Cambridge/Brookline 这三家电子券是默认),
  但 evidence 写 "default_digital_no_explicit_pickup_text"
- pickup_branches 必须能在 ../<lib_id>.json 里找到 branch_id;不能就报错并跳过
  (写到 evidence)

抽样:挑 5 个有歧义的 case,把判断理由写在 evidence,人工 review 时能复核
```

- [ ] **Step 2: Controller 抽样核对 + 数量校验**

每 lib 抽 3 个 physical_at_branch case,人肉对 evidence 看是否文本里真的有那句话(防 fabrication)。

- [ ] **Step 3: Commit**

```bash
rtk git add data/raw/branches/_pickup/*/  _classified.json
rtk git commit -m "plan-6: subagent classifies pickup_method + branch refs for 3 libs"
```

---

## Task 7: Build pipeline 集成

**Files:**
- Create: `scripts/build_branches.py`
- Modify: `scripts/build.py`
- Test: `tests/test_build_branches.py`

- [ ] **Step 1: 写 build_branches.py(失败前先写测试)**

```python
# tests/test_build_branches.py
import json, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def test_single_branch_libs_get_main_synth():
    """非多分馆 lib 应该自动获得 <lib_id>--main branch,address 从 libraries.json copy。"""
    subprocess.check_call([sys.executable, "scripts/build_branches.py"], cwd=ROOT)
    branches = json.loads((ROOT / "data/structured/branches.json").read_text(encoding="utf-8"))
    by_parent = {}
    for b in branches["branches"]:
        by_parent.setdefault(b["parent_lib_id"], []).append(b)
    # wakefield 是单分馆 lib,应有且仅有 wakefield--main
    assert by_parent.get("wakefield") and by_parent["wakefield"][0]["id"] == "wakefield--main"
    # BPL 应 >= 5(实测 26;允许 <26 但必须明显是多分馆)
    assert len(by_parent.get("bpl", [])) >= 5

def test_pass_pickup_method_attached():
    libs = {"bpl", "cambridge", "brookline"}
    passes = json.loads((ROOT / "data/structured/passes.json").read_text(encoding="utf-8"))
    seen_physical = False
    for p in passes["passes"]:
        if p["library_id"] in libs:
            assert "pickup_method" in p
            if p["pickup_method"] == "physical_at_branch":
                seen_physical = True
                assert all("--" in bid for bid in p["pickup_branches"])
    assert seen_physical, "expected at least one physical_at_branch pass across BPL/Cambridge/Brookline"
```

Run: `pytest tests/test_build_branches.py -v` → FAIL(script not found)。

- [ ] **Step 2: 实现 build_branches.py**

```python
# scripts/build_branches.py
"""Compose data/structured/branches.json from:
  - data/raw/branches/<lib_id>.json (multi-branch, subagent-extracted)
  - data/structured/libraries.json (single-branch fallback: <lib_id>--main)
"""
from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/branches"
LIBS = ROOT / "data/structured/libraries.json"
OUT = ROOT / "data/structured/branches.json"

def main():
    libs = json.loads(LIBS.read_text(encoding="utf-8"))["libraries"]
    multi = {f.stem: json.loads(f.read_text(encoding="utf-8"))
             for f in RAW.glob("*.json") if not f.name.startswith("_")}
    branches = []
    for lib in libs:
        lid = lib["id"]
        if lid in multi:
            for b in multi[lid]["branches"]:
                if not b.get("geo"): continue   # skip ungeocoded
                branches.append({
                    "id": b["branch_id"],
                    "name": b["name"],
                    "parent_lib_id": lid,
                    "address": b["address"],
                    "geo": b["geo"],
                    "hours_raw": b.get("hours_raw"),
                })
        else:
            if not lib.get("address") or not lib.get("geo"): continue
            branches.append({
                "id": f"{lid}--main",
                "name": lib["name"],
                "parent_lib_id": lid,
                "address": lib["address"],
                "geo": lib["geo"],
                "hours_raw": None,
            })
    OUT.write_text(json.dumps({
        "_meta": {"built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                  "n_branches": len(branches)},
        "branches": branches,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {len(branches)} branches")

if __name__ == "__main__":
    main()
```

- [ ] **Step 3: 改 `scripts/build.py` 在生成 passes.json 时附 pickup_method**

定位 build.py 里产出 passes 的循环(grep `pass_type` 找)。对每条 pass:

1. 若 `library_id` ∈ {bpl, cambridge, brookline}:从 `data/raw/branches/_pickup/<lib_id>/_classified.json` 查 `pickup_method` + `pickup_branches`,直接拷贝。
2. 否则 fallback:`pickup_method = "physical_at_branch" if pass_type 包含 "loan" / "physical" / "card" else "digital"`;若 physical,`pickup_branches = [f"{library_id}--main"]`;digital → `pickup_branches = []`。
3. build.py 在收尾时先 `import scripts.build_branches as bb; bb.main()`,保证 branches.json 先出。

(若 build.py 较长,只做最小侵入修改;原有产物结构不变。)

- [ ] **Step 4: 跑测试 + 跑 build,要求 100% pass**

Run:
```
python scripts/build.py
pytest tests/test_branch_schema.py tests/test_build_branches.py -v
```
Expected: 5 个测试全 PASS。若 test_pickup_branch_ids_resolve 报某 branch 不存在,回 Task 6 修 `_classified.json` 把 evidence 写清楚后人工改正。

- [ ] **Step 5: Commit**

```bash
rtk git add scripts/build_branches.py scripts/build.py tests/ data/structured/branches.json data/structured/passes.json data/structured/library_catalog.json
rtk git commit -m "plan-6: build branches.json + attach pickup_method/pickup_branches to passes"
```

---

## Task 8: 审计页升级(libraries.html + passes 视图)

**Files:**
- Modify: 生成 `audit/libraries.html` 的脚本(`scripts/build_audit*.py`,先 `grep -l "lib_id 是数据爬取模型" scripts/` 定位)
- Modify: `audit/policies.html` 或 `audit/passes.html` 生成器(若 pass 详情有视图)

- [ ] **Step 1: 删掉红框里"plan-6 工作项"那段(已落地无需再喊),保留"为何 lib_id 不是产品概念"的方法论一段**

具体改写:把红框第三段(plan-6 工作项)替换为简短一行:`✅ plan-6 已实现:见下表 branch 展开行,以及 pass 列表的 pickup_method 列。`

- [ ] **Step 2: 多分馆 lib 在明细表下方加一个**折叠 sub-table**:**

每个多分馆 lib(BPL/Cambridge/Brookline)行下挂一张子表,列:`branch_id | name | address | geo`,数据从 `branches.json` 查。审计目的:(a) 数据正确性 — 让审计直接核对 BPL 26 个分馆 vs 官方页;(b) 用户决策 — 这是用户开车去取卡的真实地址。符合 [[audit-panel-must-serve-real-decision]] 双重标准。

不要做的:
- ❌ branch 数量直方图(纯组织抽象,违反 panel rule)
- ❌ branch × pass 矩阵图(组合爆炸,无审计价值)

- [ ] **Step 3: passes 详情(若 audit 里有)新增列 `pickup_method`(badge)+ `pickup_branches`(branch_id 列表;实体券下挂第一个 branch 的 street)**

- [ ] **Step 4: 实跑生成审计页 + 人眼复查 BPL/Cambridge/Brookline 行**

Run: `python scripts/build_audit*.py`(具体文件名按现有结构);浏览器打开 `audit/libraries.html`,目视:
- 三家多分馆 lib 子表能展开
- BPL Copley 地址非 placeholder
- 红框文案干净,无 "plan-6 待办" 字样

- [ ] **Step 5: Commit**

```bash
rtk git add audit/libraries.html scripts/build_audit*.py
rtk git commit -m "plan-6: audit libraries.html shows branch sub-rows for multi-branch libs"
```

---

## Task 9: 前端按 pickup_method 切换展示

**Files:**
- Modify: `web/src/components/PassCard.tsx`(或同名 — 先 `grep -rn "pass_type\|library_id" web/src/components/` 定位)
- Modify: `web/src/data/types.ts`(加 PickupMethod / Branch 类型)
- Modify: `web/public/branches.json` 拷贝(或前端 fetch 路径)

- [ ] **Step 1: 加类型**

```typescript
// web/src/data/types.ts
export type PickupMethod = "digital" | "physical_at_branch";
export interface Branch {
  id: string;
  name: string;
  parent_lib_id: string;
  address: { street: string; city: string; state: string; zip?: string };
  geo: { lat: number; lon: number };
}
export interface Pass {
  // ... existing fields
  pickup_method: PickupMethod;
  pickup_branches: string[];   // branch ids
}
```

- [ ] **Step 2: 拷贝/暴露 branches.json 到前端可读路径**

在 `web/vite.config.ts` 或 build script 里加一条:`cp data/structured/branches.json web/public/data/branches.json`(参考 plan-3 已有的 libraries.json 拷贝方式)。

- [ ] **Step 3: 改 PassCard 渲染规则**

```tsx
// pseudo-code in PassCard.tsx
{pass.pickup_method === "digital" ? (
  <Chip>电子券 · 邮件链接</Chip>          // 不展示 library_id
) : (
  <div>
    <Chip color="warning">实体券 · 到馆取</Chip>
    <ul>
      {pass.pickup_branches.map(bid => {
        const b = branchById(bid);
        return <li key={bid}>{b.name} — {b.address.street}, {b.address.city}</li>;
      })}
    </ul>
  </div>
)}
```

- [ ] **Step 4: 起 dev server + 浏览器实测**

Run:
```
cd web
pnpm run dev
```
打开 BPL 的实体券 pass(e.g., Boston Athenaeum Reciprocal Card 之类),目视:
- 显示 "实体券 · 到馆取" 徽章
- 列出 1+ 个 branch 名 + 街道地址
- 电子券 pass 不出现 "by BPL" 字样,只显示折扣文案

如果浏览器无法在本环境跑,**显式声明 "未做端到端 UI 测试"**(对照系统提示里 frontend 验证条款)。

- [ ] **Step 5: Commit**

```bash
rtk git add web/src/ web/public/data/branches.json web/vite.config.ts
rtk git commit -m "plan-6: frontend renders pickup_method + branch addresses for physical passes"
```

---

## Self-Review Notes

- ✅ Spec 覆盖:红框 4 项工作(pickup_method 字段、pickup_branches、重抓三家、前端规则)全部对应有 task。
- ✅ 没有 TBD / "实现适当错误处理" 之类占位符。
- ✅ 类型一致:`pickup_method` / `pickup_branches` / `branch_id`(格式 `<lib_id>--<slug>`)在 Task 1/3/6/7/9 之间一致。
- ✅ TDD:Task 1 锁 schema、Task 7 锁 build 行为。Task 3/6 是 subagent 数据任务,验收靠抽样核对(数据正确性比单元测试更管用)。
- ✅ DRY:branches.json 是 single source,前端、审计、build 都从这一份读。
- ✅ YAGNI:不做 Assabet/MuseumKey 多分馆(没证据他们需要)、不做 branch 网络归属(违反 panel rule)、不做 branch 库存。
- ✅ 设计原则锚定 memory:[[product-scope-query-only]] 不引入"哪个 branch 最便利"推荐;[[audit-panel-must-serve-real-decision]] 审计页不加直方图;[[feedback-no-api-call]] LLM 提取全走 subagent。

---

**已存盘:`docs/superpowers/plans/2026-05-16-plan-6-branch-model.md`。等你审完批改,再决定 subagent-driven 还是 inline 执行。**
