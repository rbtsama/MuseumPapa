# Panel + Data 排查与优化 Plan v2（全部已核验 · 含 backup/ 交叉参考）

**日期**：2026-05-26（第二轮，取代第一轮）｜ **范围**：admin panel（`admin/`）+ 全量数据（`data/structured/`）+ 构建管线（`src/malibbene/build/`）。**用户端 `web/` 本轮不动。**
**方法**：三路并行只读审计 + 我对 4 个最高风险结论**亲自动手核验**。本版每条都标 ✅（已核验，带证据/数字）。第一轮里被推翻的结论单独列在「⛔ 已推翻 / 丢弃」节。

> 这份是**排查报告 + 路线图**，不是逐步实现计划。圈定要做的条目后，再用 writing-plans 为它们出 TDD 级实现计划。

---

## 总体判断（修订版）

数据**结构**健康：1033 条 pass 引用零孤儿、零重复对、零负价，59 馆地理齐全（子代理实测）。真正的问题在**字段取值**和**管线静默行为**。

第二轮最重要的修正：**第一轮把若干结论说错了**。最大的发现不是"我们抓不到 pass_type"，而是——**我们抓到了，却让 build 读了错误的目录**。这类"自己上一轮也会错"的地方，正是交叉核验的价值。

backup 的真实价值是**它在 3 个点上确实比我们准**（pass_type、promo_code 预订模型、closed_days），同时**它也有我们没有的错误**（museumkey 把 ferry 并进 islands）。开放对比、各取所长。

---

## ⛔ 已推翻 / 丢弃（第一轮的错判，不要再做）

- **V3（MFA 价格）不是 bug。** ✅ wakefield/mfa=$15 正确（源文本含"as of Jan 20 2026 $15"），stoneham/mfa=$10 是**忠实于 stoneham 自己尚未更新的页面**，不是我们抓漏。无需动。
- **V4（backup FREE_RE 误判）不存在。** ✅ 实测两边对"50% off"裸串都返回 `half`；我们的 `normalize_benefit` 本就是 backup 的逐字移植。两边都没这个 bug。核验时也别"以我们为准"——这条结论本身是错的。
- **A1（静态部署静默丢失反馈）夸大了。** ✅ 逐行追 `panel.js:96-104`：Vercel 上 POST 返回 HTML 200 → `r.json()` 在第 101 行 reassign **之前**就抛错 → `catch{}` 吞掉 → 控制流**照样到达第 103 行 `localStorage.setItem`**。数据**不会丢**。真问题是运营者被误导（=A2）。A1 并入 A2。
- **B1（catalog 静默丢弃未映射 pass）在死代码里。** ✅ `build_library_catalog` 全仓只有 `tests/test_build_catalog.py` 引用，`build_all.py` 根本不调它。生产无影响（除非 P4 把 catalog 重新接进管线，届时再补 warn）。
- **A5（rawslug 空 → 角标消失）当前不触发。** ✅ 1033/1033 条 pass 的 `attraction_rawslug` 都非空。仅留作潜在脆弱点，可顺手加一行兜底，不单列。

---

## P0 — 数据正确性（用户直接看到的错，最高优先）

- [ ] **P0-1（最大）build 改读 `index/` 的 pass_type。** ✅ `data/raw/assabet/index/` 有 **915/915** pass_type（physical-coupon/physical-circ/digital 三态，含 `pass_type_raw` 源文本，与 backup 同法），但 `passes.py:17` 读的是 `data/raw/assabet/catalog/`（v2 scraper，**0/921** pass_type），于是 pass_form 退化为从 LLM `coupons/` 抽取（13 个 NONE + 靠 LLM 判断）。根因：`sources_v2/assabet/catalog.py:29` 的 `_PASS_TYPE_RE` 假设 `<h5>Pass Type</h5>`，真实 markup 是 `<p class="museum-pass-pass-type">`。当前 physical_coupon=738，其中 **197 条是裸默认**（无 `old_e` 文件），**105 条被 backup 实证为 digital**（源文本写"Printable/Digital Coupon Pass (link delivered by email)"）。**影响**：~105+ 条 pass 让用户专程去图书馆取实体券，实际是邮件发码。**修**：让 `passes.py` 的 pass_form 取自 `index/` 的 pass_type（或修 v2 正则到 `museum-pass-pass-type`），重跑 build。**这是对用户最有误导性的字段。**
- [ ] **P0-2（高）8 条 "FREE" 误导。** ✅ 亲验恰好 8 条：`{lincoln,maynard,medford,melrose,methuen,middleton,natick}/jfk-library`（实为"Single ticket 50% off + Child free"）+ `milton/maplewood-day-camp`（实为 $12/child + 婴儿免费），`summary_for` 因 `free` 权重最高（_STRENGTH=6）而显示 **FREE**。**注意**：另有 200 条 FREE 是真免费（如 ma-state-parks），**不要误伤**。**修**：`build/coupons.py:summary_for()` 当存在非-free 的主受众（Single ticket/Adult/Everyone）policy 时，summary 以主受众为准，免费行作为附注。
- [ ] **P0-3（中）everett / lawrence 居住资格补 `yes`，复核 chelsea。** ✅ 我们 `passes.json`：everett、lawrence = `unknown`（没跑 probe），chelsea = `restricted:"no"`，north-andover = `yes/town`（**已正确**）。backup `cross_network_tests.json` 有同网络实测：everett(NOBLE)、lawrence(MVLC wilmington) **被拒** = 真居住限制。**且** chelsea 的 `"no"` 建立在错误前提：probe evidence 声称"same MBLN network"，但 `libraries.json` 里 bpl 的 network 是 `BPL`、chelsea 是 `MBLN`（跨网，不测居住轴）。**修**：everett/lawrence → `restricted:"yes" scope:"town"`；chelsea probe 重判或降级为 `unknown`。
- [ ] **P0-4（中）`Performance` 分类被静默丢弃。** ✅ `attractions.json` 分类计数：Children=76 / History=44 / Nature=30 / Science=22 / Art=21 / **Performance=0** / Sports=2。根因：`build/categories.py:28` 的 `RAW_TO_CANONICAL` 缺 `"Performance":"Performance"` 自映射（legacy 已存规范名 `Performance`，`canonicalize` 把它清空）。影响 **7 个景点**，其中 `wheelock-family-theatre` 只有 `["Performance"]` → **分类变空**。**修**：加自映射，重跑 build。

---

## P1 — 构建管线护栏（防止以后再静默出错）

- [ ] **P1-1（高）`validate.py` 加引用完整性并 raise。** ✅ 现状仅算 5 个百分比指标、**从不 raise**（`build_all.py:26-27` 只 print）。`slug_canonical.canonical()` 对未知 slug 原样放行 → 一个拼写错误就产出指向不存在景点的孤儿 pass，build 照样发布。**增**：pass→library/attraction 引用完整性、重复 audience 检测、分类完整性（catch Performance=0 这类）、`available_at_branches` 恒 `"all"` 告警；失败 raise。
- [ ] **P1-2（中）`build_all.py` 统一重跑 + 跨文件一致性。** ✅ `_meta.built_at`：passes.json=5/25T16:37，libraries/attractions/branches=5/22T18:25（晚 3 天），说明 passes 被单独重跑而非走 `build_all.py`。**增**：跨文件时间/source 一致性校验；统一时间格式（catalog 用 `%Y-%m-%dT%H:%M:%SZ`，passes 用 `isoformat()` 带微秒，无法直接比对）。
- [ ] **P1-3（低）删死函数。** ✅ `build/coupons.py:153 restrictions_block()` 无任何调用方（grep 仅定义 + 旧 plan TODO），docstring 还引用旧 schema。删。
- [ ] **P1-4（低）B2 restrictions 取值优先级反了。** ✅ `passes.py:65` 让 legacy `old_e.restrictions` 盖过权威 `crec`，而同函数 :64 对 coupon 本身是 `crec` 优先。**实测影响仅 1 条**（不是第一轮说的 113），但为原则一致性仍应修：`crec` 有 restrictions 时优先。
- [ ] **P1-5（低）catalog.py 死代码但被测试，给假信心。** ✅ `tests/test_build_catalog.py` 4 个测试跑的是不在生产路径的 `build_library_catalog`。**决策**：要么删 catalog.py + 测试，要么 P4 把它接回管线作为 pass_type 权威源（与 P0-1 合并考虑）。

---

## P2 — Admin Panel Bug + 健壮性

- [ ] **P2-1（高）A2 只读模式横幅（并入 A1）。** ✅ 静态部署无 `/api/overrides`，所有审计只进 localStorage，但 `panel.html:70` 文案写"可喂回构建管道"。数据虽不丢（见 ⛔A1），但运营者误以为进了共享 store。**修**：探测 `/api/overrides` 返回非 JSON（content-type / parse 失败）→ 顶部横幅"⚠ 只读模式：审计仅存本地，请用导出"；同时去掉无意义的 POST。
- [ ] **P2-2（高）跨模式静默丢失（新发现，比 A1 更真）。** ✅ `auditLoadAll`（panel.js:93-94）服务器可达就用服务器、否则 localStorage，**两者从不 merge**。先用静态部署写满 localStorage，再开 python 版 → 返回服务器 store、本地反馈不可见，下次 `auditPut` 覆盖丢失。**修**：load 时合并两源（按 target 取最新）。
- [ ] **P2-3（中）A4 两套资格判定打架。** ✅ 矩阵用 `panel.logic.mjs:residencyOk`，详情弹窗内联另写 `resolvePass→checkL3Residency`（panel.js:214-220）。`restricted:"yes"` 但 scope 缺失/异常时：矩阵显示干净 A 档（无 ⚠），弹窗显示 ⚠ warn——**互相矛盾**。`panel.logic.test.mjs` 未覆盖这个 case。**修**：删内联版，统一 import `panel.logic.mjs`，补该 case 的测试。
- [ ] **P2-4（中）A3 `loadData` 全有或全无。** ✅ `panel.js:139-151` `Promise.all` 5 个 fetch，任一失败整页"加载失败"。而 `branches.json` 索引建好后（`branchesByLib` 176-179）**全程没被读过**——缺它崩主矩阵纯属白崩。**修**：`Promise.allSettled` + branches 缺失降级为 `[]`（并清理死的 branchesByLib）。
- [ ] **P2-5（中）A6 `onlyEligible` 暗中排除 warn 格。** ✅ `panel.js:447` `!(tier==="a" && !rz.warn)` 把居住未知（warn）的 A 档格也藏了，而独立的"⚠无法确认居民限制"勾选项（`d-warn`）只控制 ⚠ 字形、无法把 warn 格找回来。两控件语义冲突。**修**：明确语义二选一。
- [ ] **P2-6（低）A7 死代码清理。** ✅ `updateStat()` 无调用 + `#stat-summary` 恒隐藏；`auditRenderLog(showPaths)` 从不传参 → 磁盘路径分支死；`STATE.showOnlyCovered/activeLens/categoryFilter` 声明未用。清理。
- [ ] **P2-7（低）A8 保存反馈 UX 不一致 + 新增 verified_ok 漏项。** ✅ "通过审查"留弹窗带 note，"保存反馈"关弹窗无提示，均无取消键。另：`verified_ok` 状态缺在日志 emoji 表（panel.js:1049）和状态筛选 `<select>`（panel.html:105-111），无法过滤。**修**：统一交互 + 补 verified_ok。
- [ ] **（非 bug，记录）** XSS 不存在（`el()` 走 `createTextNode` 自动转义）；筛选默认值 HTML 与 STATE 一致；监听器不重复挂载；现有测试 **24 pass / 0 fail**。

---

## P3 — 数据清洗（展示用，低风险）

- [ ] **P3-1 `summary` 浮点 `$N.0/person`。** ✅ 31 条（`$9.0`/`$13.5`/`$2.0`…）。`summary_for()` 整数化 float 去 `.0`，保留 `$9.5` 真小数。
- [ ] **P3-2 重复价格行 + 错 age_range。** ✅ 17 个景点；`new-england-aquarium` 9 行（3 套票档 × 成人/儿童/老人）全被错打 `age_range{3-11}`（从儿童列复制）。**修**：build 抽价阶段按受众去重、修 age_range、套票分档加标签。
- [ ] **P3-3 重复 audience 行。** ✅ 60 条（多为 Child×2：付费 + 婴儿免费）。**修**：把免费婴儿行改 `Child (under 2)`，或在 schema/validate 明确唯一键 `(audience, age_range)`，防前端按 audience 去重吞掉免费行。
- [ ] **P3-4 `the-childrens-piazza` 价格倒挂。** ✅ adult=$6 / child=$12（均 age_range null，来源"legacy snapshot"）——几乎肯定标反。核实修正。
- [ ] **P3-5 `museum-of-african-american-history` 空壳。** ✅ 仅 name，website/geo/description/categories/prices 全空，却挂 2 条 pass。回填元数据。
- [ ] **P3-6 B3 误标的 ferry 文件。** ✅ `data/raw/pass_coupons/hingham_boston-harbor-islands.json` 实体是 ferry（"Will-Call window"），BOGO 被错抽成 `percent-off 50`，且 museumkey map 把 "ferry" 名并进 islands（与 `slug_canonical.py:63` 刻意保留两者相反）。**修**：改名/重抽到正确 slug + 修 museumkey map。
- [ ] **P3-7 低优杂项。** ✅ 5 景点缺 geo（hale-reservation / mass-audubon / mass-audubon-wildlife-sanctuary / maah / paul-revere-heritage-site，部分可从 legacy `geo.json` 恢复）；2-3 条 description 有替换符 `�`（armenian-museum / paul-revere-house / cohasset mfa coupon）；3 条 website 空串应改 null；20 条 `% off` summary 但景点无 `prices`（用户算不出折后价）。
  - **给前端的提醒（本轮不改 web/，仅记录）**：经纬度字段名是 `lat`/**`lon`**（非 `lng`）；placeholder 文件名小写（`art.svg`）而 category 首字母大写（`"Art"`）——前端须 lowercase 再查，否则 fallback 静默失败。

---

## P4 — 从 backup 借鉴的增强（核实后做）

- [ ] **P4-1 closed_days 派生（便宜）。** ✅ 我们 `attractions.json` 的 `closed_days` 0/96 非空，但**已存逐日 `hours`**（mfa tue=closed 等）——可确定性派生 `[day for day,v in hours.items() if v=="closed"]`，比 backup 的独立研究产出更准。
- [ ] **P4-2 promo_code 预订模型（backup 更准）。** ✅ backup 把 BCM/ICA/ISG/MFA/PEM 标 `booking_model:"promo_code"`（拿馆码到景点官网二次预订）并带可执行 note；我们对 PEM/MFA 标 `walk_in_ok` **是错的**（误导用户直接走进去）。**做**：逐个核实这 5 馆现状后，补 `booking_model` 枚举 + `booking_note`。
- [ ] **P4-3 pass_type 两源对账（gated on P0-1）。** ✅ 我们 `snapshot_diff.py` 已移植 backup `diff_catalog.py` 且更广（prev-vs-current）。值得再借 `check_passtype_discrepancies.py` 的思路：scrape 的 pass_type vs 独立真值源做 NEW-ONLY / MISSING / DISAGREE 三桶对账。**前置**：先做 P0-1 让 build 读对 pass_type，此告警才有意义。

---

## 已核验的 backup 对比小结（三人行）

| 维度 | 谁更准 |
|---|---|
| pass_type 抽取 | **backup**（我们抓到了却读错目录，P0-1） |
| promo_code 预订模型（PEM/MFA） | **backup**（我们 walk_in_ok 是错的，P4-2） |
| closed_days | backup 已填；但我们 hours 数据更richer，可自行派生（P4-1） |
| coupon 逐条 source_phrase 溯源 | **我们** |
| build fail-closed 护栏 | **我们**（backup 无） |
| canonical slug 纪律（ferry≠islands） | **我们**（backup 把它们并了，B3 根因） |
| 相对日期 blackout `{month,day}` | **我们**（backup 存绝对日期会过期） |
| 覆盖范围 | **我们** 59 馆 vs backup 15 馆 |
| normalize_benefit / diff | 打平（同源移植） |

---

## 建议执行顺序

1. **P0-1**（pass_type 读对目录）——单点影响最大、对用户最误导。
2. **P0-2 / P0-3 / P0-4** 其余数据正确性 + **P1-1**（validate raise，防回归）。
3. **P2-1 / P2-2 / P2-3**——直接影响你用面板收反馈的可靠性，改动小。
4. **P3 清洗** + **P1 其余护栏** 随手做。
5. **P4 增强** 视核实结果推进（P4-2 PEM/MFA 现状需先确认）。

> 置信度：本版所有条目均 ✅ 已核验（数字/代码引用在各条内）。你圈定条目后，我用 writing-plans 出 TDD 实现计划。
