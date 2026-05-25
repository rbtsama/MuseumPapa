# Panel + Data 排查与优化 Plan（含 backup/ 交叉参考）

**日期**：2026-05-26 ｜ **范围**：admin panel（`admin/`）+ 全量数据（`data/structured/`）+ 构建管线（`src/malibbene/build/`）。**用户端 `web/` 本轮不动。**
**方法**：三路并行只读审计（admin / data+build / 朋友的 `backup/` 交叉参考）+ 我对头部结论亲自核验。

---

## 我的总体判断

数据的**结构**是健康的：1033 条 pass 的 `library_id`/`attraction_slug` 引用零孤儿、零重复对，59 馆地理信息齐全。真正的问题集中在**字段取值的正确性**和**管线的"静默"行为**上——也就是"看起来有值、其实是默认值或抓错了"的地方。`backup/`（朋友的实现）最大价值不在代码，而在它**新鲜抓取的 pass_form** 和**实测的跨网络资格**——这两块正好戳中我们最薄弱的盲点。

下面按"先核验、再修正、后增强"分层。每条标了**置信度**（✅已核验 / ⚠需核验）。

---

## 阶段 0 — 先核验（动手修之前必须确认事实）

这些是高影响但带不确定性的结论，先查清楚再决定怎么改，避免照着 backup（它本身也可能错）盲改。

- [ ] **V1（最高优先）pass_form 到底有多少是"默认值"而非真实抓取。** ✅机制已确认：`build/passes.py:34` 默认 `physical_coupon`，`:55` 仅从 legacy `old_e` 取 pass_form，否则就是这个默认。当前分布 physical_coupon=738。需要查：738 里有多少来自真实 `old_e`、多少是裸默认？逐条对照 `backup/library_catalog.json`（5/25 新抓，含 `pass_type`）。**这是对用户最有误导性的字段**（决定要不要专门跑一趟图书馆取实体券）。
- [ ] **V2 Chelsea / Everett / Lawrence / North-Andover 的居住资格。** ⚠我们 `passes.json` 里 `chelsea/museum-of-science` 是 `residency_restriction.restricted="no"` 且 `source="booking_probe"`；但 `backup/cross_network_tests.json` 的 Playwright 实测显示 NOBLE/MVLC 卡在这几个馆**被拒**。需要复核我们的 booking_probe 是不是假阴性。若属实，这 4 个馆的 `card_eligibility` 和相关 pass 的 residency 要改。
- [ ] **V3 MFA 价格按馆差异。** ⚠`wakefield/mfa=$15`（新价，文本含"as of Jan 20 2026 $15"），`stoneham/mfa=$10`。核对 stoneham 源文本是否真还是 $10（各馆更新文案时间不一），还是我们抓漏了更新。
- [ ] **V4 backup 自身的已知错误**别被带偏：其 `normalize_benefit.py` 的 `FREE_RE` 早于 `HALF_PRICE_RE`，把 ~35 个馆的 "Museum of Science 50% off" 误判成 "Free"——**我们这边是对的**，核验时以我们为准。

---

## 阶段 1 — 数据正确性 Bug（修正）

- [ ] **D1 `Performance` 分类被静默丢弃。** ✅已核验：`attractions.json` 里 **0** 个景点带 `Performance`，但 `CANONICAL` 列表声明了它。根因：`build/categories.py` 的 `RAW_TO_CANONICAL` 没有 `"Performance": "Performance"` 自映射，导致 legacy 存的规范名 `Performance` 落空。影响 7 个景点（剧院/乐团类），任何按 Performance 过滤永远空。**修**：`categories.py` 加 `"Performance": "Performance"`（含 `Sports` 一并检查），重跑 build。
- [ ] **D2 `museum-of-african-american-history` 景点记录近乎空壳。** ✅已核验：只有 `name`，`website/geo/description/categories/prices` 全空，却挂着 2 条 pass。**修**：补抓该景点元数据（backup 的 `maah` slug 在 cambridge/brookline 的 LibCal catalog 里可能有源）。
- [ ] **D3 `summary` 浮点格式 `$N.0/person`。** ✅已核验 20 条（如 `$10.0/person`）。**修**：`build/coupons.py` 的 `summary_for()` 对整数化的 float 去掉 `.0`（保留 `$9.5` 这类真小数）。
- [ ] **D4 重复 audience 行不是唯一键。** ✅已核验 60 条（多为 `Child` 两行：付费儿童 + "2岁以下免费"）。数据本身没错，但 `audience` 不唯一。**修**：要么把免费婴儿行的 audience 改成 `Child (under 2)`，要么在 schema 文档/`validate.py` 里明确"唯一键是 (audience, age_range)"，防止前端按 audience 去重时吞掉免费行。
- [ ] **D5 price 行重复。** ⚠数据 agent 报多个景点同一 audience 出现 2–8 次（LLM 抽价多句重复）。仅展示用、不影响优惠逻辑，但前端会乱。**修**：build 抽价阶段按 (audience) 去重保最优/最新。

---

## 阶段 2 — 构建管线健壮性（防止以后再静默出错）

- [ ] **B1 catalog 静默丢弃未映射 pass。** ⚠`build/catalog.py` 的 `_canonical_slug()` 对没进手工映射表的 LibCal/MuseumKey pass 返回 `None`，只记 `n_unmapped` 不报错。museumkey 映射表只有 21 条，新增馆会无声消失。**修**：build 末尾若 `n_unmapped>0` 至少 WARNING（或可配置 raise）。
- [ ] **B2 restrictions 取值优先级反了。** ⚠`build/passes.py:65` 让 legacy `old_e.restrictions` 盖过权威 `crec`（pass_coupons）的 restrictions，而同函数对 coupon 本身却是 `crec` 优先（:64）。113 条非空 restrictions 受影响、来源不一致。**修**：`crec` 有 restrictions 时优先 `crec`，`old_e` 只作回退。
- [ ] **B3 误标的原始文件。** ⚠`data/raw/pass_coupons/hingham_boston-harbor-islands.json` 实体是 `boston-harbor-island-ferry`（slug 不匹配），含 50% off，与实际生效的 legacy BOGO 矛盾。当前靠"运气"用了对的 legacy 数据，但 guard 看不见它。**修**：重命名/重抽到正确 slug，或删除。
- [ ] **B4 `validate.py` 太薄。** ✅只报 5 个百分比指标、不 raise。**增**：加引用完整性（pass→lib/attraction）、重复 audience、`available_at_branches` 恒为 `"all"`、分类完整性（Performance=0 这类）、跨文件 `_meta` 时间偏移检查。
- [ ] **B5 `_meta` 时间偏移。** ✅已核验：`passes.json`(5/25) 比 libraries/attractions/branches(5/22) 晚 3 天，说明 passes 被单独重跑而非走 `build_all.py`。无跨文件一致性校验。**修**：`build_all.py` 统一重跑并加跨文件 `source_hash`/时间一致性检查。
- [ ] **B6 死函数 `build/coupons.py:restrictions_block()`（旧 schema，无人调用）。** ✅删。

---

## 阶段 3 — Admin Panel Bug + 健壮性

- [ ] **A1（关键）静态部署上 `fetch` 把 HTML 当 JSON。** ✅已确认模式：Vercel SPA rewrite 让任何缺失路径返回 `index.html`（200）。`auditLoadAll`/`auditPut`/`auditRevoke`（`panel.js:93/99/108`）只判 `r.ok` 就 `r.json()`，HTML 200 → 解析抛错 → 被 `catch{}` 静默吞掉 → 落 localStorage 但**用户毫不知情**；`auditPut` 还可能在抛错后漏掉 `localStorage.setItem` 造成**静默丢失刚存的反馈**。**修**：fetch 后检查 `Content-Type` 含 `application/json` 再 parse；POST 失败时确保落 localStorage。（这正是上次 `town_zips` 那个 `Unexpected token '<'` 的同类根因。）
- [ ] **A2 只读模式无提示。** ✅静态部署无 `/api/overrides` 后端，所有审计只进 localStorage，但侧栏文案暗示能"喂回构建管线"。**修**：检测 `/api/overrides` 不可用 → 顶部显眼横幅"⚠ 只读模式：审计仅存本地，请用导出"。
- [ ] **A3 `loadData` 全有或全无。** ✅`Promise.all` 5 个 fetch，任一失败整页崩。`branches.json` 只在详情弹窗用到，缺失不该崩主矩阵。**修**：`Promise.allSettled` + 缺失降级（branches 缺 → `[]`）。
- [ ] **A4 详情弹窗判定与矩阵格子判定走两套代码。** ⚠`panel.js` 内联重写了 `checkL1/L3/L4`（`resolvePass`），而矩阵用的是 `panel.logic.mjs` 的 `cardOk/residencyOk`。两者对"restricted=yes 但无 scope"等可能给出**互相矛盾**的结论。**修**：删内联版，统一 import `panel.logic.mjs`。
- [ ] **A5 `attraction_rawslug` 可能 undefined → 角标永不命中。** ⚠`passAuditStatus`（`panel.js:116`）用 `rawslug` 拼 key，若该字段空则角标静默消失。**修**：`rawslug ?? attraction_slug` 兜底。
- [ ] **A6 `onlyEligible` 暗中也排除了 warn（居住未知）的 A 档格。** ⚠`panel.js:447`，与单独的"⚠无法确认居民限制"勾选项语义冲突、无提示。**修**：明确语义，二选一。
- [ ] **A7 死代码 / 不可见 UI。** ✅`updateStat()` 无人调用且 `#stat-summary` 恒 `display:none`；`auditRenderLog(showPaths)` 永远不传参→磁盘路径功能失效；`STATE.showOnlyCovered/activeLens/categoryFilter` 声明未用。**修**：清理或修复。
- [ ] **A8 保存反馈无"取消"按钮 + 与"通过审查"反馈不一致。** ✅一个关弹窗无提示、一个留弹窗带提示。**修**：统一交互 + 加取消。

---

## 阶段 4 — 清理（低风险、高可读性收益）

- [ ] **C1 `panel.css` ~50%（~250 行）死样式。** ✅旧 `.matrix/.cell/.pill/.sim-*/.lens-*/.adm-table/.group-header/.verdict/.avail/.override-editor` 等当前 `panel.js` 都不再产出。`#auditor-name`/`#lib-filter` 指向不存在的元素。**修**：整理删除。
- [ ] **C2 `panel.audit.mjs` 残留。** ✅`controlsFor`、`CORRECTION_KIND`、一堆 enum 数组只被测试引用、生产不再用；`buildRecord` 的 `corrected` 分支已无 UI 入口。**修**：精简（保留 `verified_ok` 仍用的 `buildRecord` 主体），同步删对应测试。
- [ ] **C3 `AUDIT_LS_V3` 暗示有迁移但其实没有。** ✅改名或加迁移注释。

---

## 阶段 5 — 从 backup 借鉴的增强（盲点补齐）

- [ ] **E1（高价值）修 pass_form 数据源。** 我们的 Assabet catalog 抓取拿不到 "Pass Type"（它在 `/by-museum/<slug>/` 详情页，不在索引页），导致大量 pass_form 走默认。**做**：要么改 scraper 抓详情页 pass_type，要么把 `backup/library_catalog.json`（5/25 新抓）的 pass_type 作为权威种子导入。先做阶段0-V1 确认规模。
- [ ] **E2 派生 `closed_days[]`。** 我们有逐日 hours 字符串但 `closed_days` 恒 `[]`；backup 显式派生。**做**：build 的 attraction 阶段从逐日 hours 派生闭馆日数组（为将来日历视图打底）。
- [ ] **E3 `booking_model` 细化（尤其 `promo_code`）。** backup 把 BCM/ICA/ISG/MFA/PEM 标为 `promo_code`（需先在景点官网用码二次预订），我们 `reservation.required` 把 BCM/PEM 标成 `walk_in_ok` ⚠可能错。**做**：核验后补一个更可执行的预订模型字段 + `booking_note`（给用户一句话操作指引）。
- [ ] **E4 移植 `check_passtype_discrepancies.py` 思路。** 在 build 里做"本次抓取 vs 上次快照"的 pass_type/pass_form 差异告警（配合现有 `snapshot_raw.py`，补一个 diff 步骤）。

---

## 建议执行顺序

1. **先做阶段 0 核验**（V1 pass_form 规模、V2 Chelsea 居住）——决定阶段 1/5 的具体改法。
2. **阶段 3（A1/A2/A3）** admin 关键 bug——直接影响你现在用面板收反馈的可靠性，且改动小、风险低。
3. **阶段 1 数据 bug（D1/D2/D3）** + **阶段 2（B1/B4）** 管线护栏。
4. **阶段 4 清理** 随手做。
5. **阶段 5 增强（E1 最值钱）** 视核验结果推进。

> 说明：本文件是**排查报告 + 路线图**，不是逐步实现计划。你圈定要做的条目后，我再用 writing-plans 为这些条目出 TDD 级实现计划。置信度：✅=我已亲自核验数据/代码；⚠=来自子代理审计、建议先做阶段0核验。
