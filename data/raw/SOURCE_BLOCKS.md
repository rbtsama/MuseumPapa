# Source-block extraction — durable archive & re-extraction runbook

> 本文件记录 **source-block 抽取**(plan: `docs/plan_source_block_extraction.md`)这一次完整跑批
> 落地的全部原始数据与产物，以及"以后再抽取时如何复用、不必重跑"的操作手册。
> 抓取/抽取时间：**2026-05-29 ~ 2026-05-30**(美西时间)。

## 0 · 三层数据结构(项目核心资源)

整个 Coupon Map 项目的本质,是把散落在各景点 / 图书馆官网、非结构化的优惠信息,
变成可结构化查询的数据。为此原始数据分三层,层层可追溯:

| 层 | 名称 | 内容 | 落地位置 | 性质 |
|---|---|---|---|---|
| **第 1 层** | 原始页面 | 从官网爬下来的每个景点 / 图书馆的原始 HTML 页面 | `attractions/{pages,subpages}/*.html`、`libraries/_pages/*.html`(均已入 git) | 原始数据,不可再生 |
| **第 2 层** | 原始内容抽取 | 每条事实**出自原文的哪一段**(价格段落、Resident 政策原话…)的 verbatim 段落 | `attractions/_source_blocks/*.json`、`libraries/_source_blocks/*.json`(`source_block` / `source_phrase`);`_stripped/` 是 1→2 的中间正文 | 仍属原始数据 |
| **第 3 层** | 结构化数据 | 对原文解读后抽象出的判断(价格数值、Yes/No、营业时间…),按设计的 schema 填入 | `data/structured/*.json` | 派生 / 可重算 |

规则:
- **机器无法解析 / 判断的信息** → 暂时搁置(第 2/3 层诚实写 `null`,绝不臆造)。
- **人工 edit 的内容** → 直接归到**第 3 层**(经 `data/overrides/`,在 build 时叠加;sync 时按字段深合并 `_evidence`,不覆盖第 2 层 `block`)。
- **以后发现新页面 / 新说明** → 补进**第 1 层(新 HTML)或第 2 层(新 source_block)**,再一路推导到第 3 层。这是一个长期持续的过程。
- 前端两个浮窗 + 侧边栏的 "Sources" 区,渲染的就是**第 2 层**段落,供用户 / reviewer 核对第 3 层数值。

## 1 · 这次跑了什么

为 `data/structured/` 里每条事实附上**官网原文 1–3 段 verbatim 段落**(`source_block`)，
供 audit 时人工核对结构化数值。范围 155 个实体：96 景点 + 59 图书馆。

四阶段：A 抓深层子页 + 图书馆办卡页 → B 每实体一个隔离 subagent 抽取 → C 合并进 build 管线 → D 前端渲染。

## 2 · 哪些是"不可再生 / 已永久保存"的原始数据

| 目录 | 内容 | 是否入 git | 说明 |
|---|---|---|---|
| `attractions/pages/<slug>.html` | 景点首页 HTML (85) | ✅ **force-add 入库** | 原 `.gitignore` 第 46 行排除 `*.html`，本次已强制纳入 |
| `attractions/pages/<slug>.meta.json` | 首页 url/title/og_image (48) | ✅ | |
| `attractions/subpages/<slug>__<sub>.html` | 景点深层页 HTML (321) | ✅ **force-add 入库** | 原 `.gitignore` 第 47 行排除，本次已强制纳入 |
| `libraries/_pages/<lib_id>.html` | 图书馆办卡页 HTML (57) | ✅ | 未被 gitignore |
| `attractions/_stripped/<slug>.txt` `libraries/_stripped/<lib_id>.txt` | 从 HTML 蒸馏出的可读正文(带 `=== <file> ===` + `source_url:` 头)；**这是 Phase B subagent 真正读取的输入** | ✅ | 142 个 |
| `attractions/_source_blocks/<slug>.json` `libraries/_source_blocks/<lib_id>.json` | **抽取产物**(verbatim 段落 + source_phrase + url + confidence) | ✅ | 96 + 59 |
| `_prompts/<kind>__<id>.txt` | 派给每个 subagent 的完整 prompt(§7 verbatim + 占位符已填) | ✅ | 142 个 |
| `_source_block_manifest.json` | 派工清单(实体→类型/名称/stripped 路径/sources_inspected) | ✅ | 142 条 |
| `data/.cache/<sha1>.html` | http.fetch 24h 缓存 | ❌ gitignore | **会过期，不可依赖** |

> 结论：**原始 HTML、蒸馏正文、抽取产物三者现在全部在 git 里，缓存过期也不会丢。**

## 3 · 这次的产出统计

- 抓取：景点首页 85/96(11 家无可达 website)、景点子页 321、图书馆办卡页 57/59
  (tewksbury、arlington 返回 403，按规范静默跳过)。
- 抽取(`_source_blocks`)：
  - prices：354 行填充 / 318 高置信
  - hours：80 填充 / 74 高置信
  - reservation：72 填充 / 24 高置信
  - visitor_eligibility：2 填充 / 1 高置信
  - 图书馆 card_eligibility：47 填充 / 43 高置信 / 12 null(2 个 403 + 10 个办卡页是无正文的首页，含两家 MuseumKey 馆 cohasset/hingham)
- 13 个实体写了诚实的全 null stub(11 景点无 HTML + the-childrens-piazza 页面无正文 + 2 图书馆 403)。

## 4 · 以后怎么复用、不重跑

### 4.1 只想换 prompt / schema / 模型 重新抽取(最常见)
**不用重抓、不用重新清洗。** Phase B 读的是 `_stripped/*.txt`，已入库。
1. (可选)改 prompt 模板：`scripts/extract_source_blocks.py` 里的 `_S7` / `_SCHEMA_*`。
2. 重新生成 prompt：`python scripts/extract_source_blocks.py prompts`
3. 重派 subagent(controller 按 `_source_block_manifest.json` 每实体一个 general-purpose subagent，
   prompt 用 `data/raw/_prompts/<kind>__<id>.txt`)。**幂等技巧**:只给 `_source_blocks/<id>.json`
   还不存在/想刷新的实体派工即可。
4. `python scripts/build_all.py` → `node coupon-map/scripts/sync-data.mjs`。

### 4.2 想用不同算法重新清洗 HTML→文本
原始 HTML 已入库，直接重跑：
`python scripts/extract_source_blocks.py strip`(改 `strip_html()` / `PER_PAGE_CAP` 后)。

### 4.3 想补抓新页 / 新实体
`python scripts/crawl_subpages.py` —— **幂等**:已存在的 `<slug>__<sub>.html` 跳过，只抓缺的。

### 4.4 合并进结构化数据
`build/attractions.py::_apply_source_blocks` 与 `build/libraries.py` 在 `apply_overrides` 之后
叠加 `_source_blocks`；`coupon-map/scripts/sync-data.mjs` 按字段深合并 `_evidence`(不覆盖 block)。

## 5 · 关键脚本
- `scripts/crawl_subpages.py` — Phase A：发现+抓深层页(关键词启发式选 ≤3 候选链接) + 图书馆办卡页。
- `scripts/extract_source_blocks.py` — Phase B 准备：`strip`(HTML→正文) / `stubs`(无 HTML 实体写 null) / `prompts`(生成派工 prompt) / `all`。
- 实际 LLM 抽取由 controller 派 subagent 完成(铁律：脚本内不调 Anthropic API)。
