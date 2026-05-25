# Admin Panel v2 · 设计文档

> 起草日期：2026-05-25
> 前置文档：`docs/specs/2026-05-20-admin-panel-redesign.md`（业务/数据模型分析，仍有效）
> 本文档定义 v2 面板"长什么样、怎么交互、数据怎么存"，是实现计划的依据。

---

## 一、目标：把面板收敛成两个核心用途

现面板（`admin/panel.html` + `panel.js`）实现了 4 个 Lens + 漏斗模拟器 + 网络分组透视表，是"reviewer 自查的多维透视台"。v2 把它收敛成**给个人/客服实际用**的两件事：

1. **模拟持卡查询**（像电话客服后台）：输入"持哪几张卡 + Home Zip + 日期 + 想去的景点"，立刻看到这些卡在哪些景点有优惠、优惠是什么、怎么领、去哪预订。
2. **审计纠错**：发现结论或取值错了，用表单（不写 JSON）改正，记一条可回流构建管道的覆盖；改动实时持久化、跨本地/Vercel 共享。

核心产品原则不变：**宁可漏推一条，也别推错一条**。

---

## 二、相对现状的取舍

| 现状 | v2 |
|---|---|
| 4 个 Lens（A/B/C/D）切换 | **删除**。改成单张大宽矩阵 |
| 顶部漏斗模拟器 | **删除**。矩阵本身就是"卡+Zip+日期→资格"的实时模拟 |
| 卡 = 联盟（一联盟一张卡） | **改为按具体图书馆勾选**（联盟只用于分组） |
| 审计人 `audited_by` | **删除**（个人/共享使用，不区分人） |
| 双导出（overrides / bundle） | **合并**为可选的"下载副本"；主存储是单个文件 |
| 改值写 JSON textarea | **改为表单控件**（按字段数据类型给下拉/数字/多选/开关） |
| 审计存 localStorage（刷新丢、不共享） | **改为单文件持久化 + 跨本地/Vercel 共享** |
| Pass 改值回流不了（slug 不对齐） | **修复** raw/canonical slug 对齐 |

保留复用：资格引擎（L1–L10 funnel）、override 合并 schema、网络分组渲染骨架、数据加载与索引。

---

## 三、整体布局与交互

**左边栏 = 全部操作区；右边 = 一张大宽矩阵，第一行 + 第一列冻结。**

```
┌─ 左边栏（全部操作）──┐┌─ 右边：单张大宽矩阵（第一行+第一列冻结）──────────┐
│ 持卡（多选，按网络分组）││           ║ NOBLE …        ║ MVLC …               │
│ HomeZip [01880]        ││  景点 ⇩    ║ Wake Read Lynn ║ Wilm And …           │
│ 日期 [2026-05-25]      ││ ═══════════╬════════════════╬══════════════════════│
│ 景点过滤（多选，默认全）││  MFA       ║ ▮50  ▮FR   ·   ║ ▮$5  ·               │
│ □ 只看可订             ││  MoS       ║ ▮FR  ·    ▮bk  ║ ·    ▯tn             │
│ ── 显示选项（独立勾选）─││  Aquarium  ║ ·    ▮$5   ·   ║ …                    │
│ □ 人群条款全展开       ││                                                    │
│ □ 优惠具体值           ││  格子 = 资格档底色 + ▮/▯库存 + 勾出来的详情          │
│ □ 资格拦截层+原因      ││         + hover ⓘ原文 + ✎审计                      │
│ □ 原文内联             ││                                                    │
│ □ 怎么领文字           ││                                                    │
│ □ 库存 / □ 距离 / □ 限制││                                                   │
│ ── 审计 ──             ││                                                    │
│ 修改数 12 [下载副本]   ││                                                    │
│ [审计记录日志 ▾]       ││                                                    │
└────────────────────────┘└────────────────────────────────────────────────────┘
```

交互模型：

1. 左栏任意条件变化 → 矩阵实时重算。
2. **矩阵是唯一主视图**。详情**内联进格子**：左栏勾哪个维度"更详细"，格子里对应内容就长出来（不再有独立的下栏/抽屉）。
3. **冻结**：第一列（景点名）横向滚动不动；第一行（网络 + 馆列头）纵向滚动不动。
4. **ⓘ**：hover 显示原文片段 + 来源链接；没有就显示"无原文记录"。
5. **✎ 审计**：小笔图标，点开只有"通过 / 修改"两项（详见第八节）。

---

## 四、矩阵语义

### 4.1 资格档底色（a/b/c/d）

对每个**存在 pass** 的（景点 × 馆）格子，跑资格引擎得两个布尔：

- **卡符合** = 持有这家馆接受的卡（L1：持本馆卡，或本馆把取 pass 开放给你所在网络/全 MA）
- **Zip符合** = Home Zip 满足取 pass 居住资格（合并 L3 取 pass 资格 + L4 景点 residency）

| 档 | 条件 | 底色 |
|---|---|---|
| (a) | 卡✅ & Zip✅ | 绿 |
| (b) | 缺卡 & Zip✅ | 黄 |
| (c) | 有卡 & Zip✗ | 橙 |
| (d) | 卡✗ & Zip✗ | 灰 |

- **没 pass** 的格子 = 空白，不上色。
- **unknown 资格**：按"通过"算（不挡），格子加 ⚠ 角标"资格未确认"——这正是要审"大前提"的入口。

### 4.2 可订状态（▮/▯）——只受日期影响，不参与过滤

读该 pass 在选定日期的 `availability`：
- `available` → ▮ 可订（实心）
- `booked` / `closed` → ▯ 订满/闭馆（空心）
- `unknown` → ▮?（实心带问号）
- 未选日期 → 不画状态点，只有底色

日期只改这个状态点；没库存也照常显示该格（优惠长期稳定，今天没明天可能有）。

### 4.3 行排序（景点）

每个景点行按**该行所有格子里"最优的那个"**排：
1. 资格档：a > b > c > d
2. 同档：有可订格子 > 全订满
3. 再同：景点名字母序兜底

### 4.4 列裁剪 / 列排序（默认）

- **列裁剪**：当前景点筛选下，对所有可见景点都无 pass 的馆，整列隐藏。
- **列排序**：你持卡的网络/馆自动排到最左，方便先看自己的卡。

---

## 五、四个筛选 + 行为语义

筛选栏（全在左边栏）：持卡（多选）/ Home Zip（单值）/ 日期（单天）/ 景点（多选，默认全选）/ □只看可订。

| 筛选 | 行为 |
|---|---|
| 图书馆卡（多选） | 缺/不匹配 → **往下排，不隐藏**（假设用户哪天会补卡） |
| Zip Code（单值） | 不符合 → **往下排，不隐藏**（假设信息可能补全/其实可行） |
| 日期（单天） | **只影响可订状态标签**，不过滤 |
| 景点（多选，默认全选） | **唯一的真过滤**：取消某景点 = 真不显示该行 |
| □ 只看可订 | **真过滤**：隐藏所有非 (a) 的格子；整行变空的景点也隐藏。让用户直观看到真实覆盖面 |

---

## 六、显示选项（独立勾选，逐维度）

无总开关。每个维度一个独立 checkbox，**勾上 = 更详细，默认不勾 = 更简洁**。可任意组合。

| 维度 | 不勾（简洁） | 勾上（详细） | 数据来源 |
|---|---|---|---|
| 人群条款 | 只显示最优一条 | 摊开全部 `audience_policies` | `coupon.audience_policies[]` |
| 优惠呈现 | 只显示"有/无优惠" | 显示具体 form+value | `coupon.summary` |
| 资格判定 | 只色块徽章 | 写明拦在哪层 + 原因 | 引擎 verdict |
| 原文 ⓘ | 收成 hover 浮层 | 直接内联展开 | `source_phrase(_block)` |
| 怎么领 | 只一个图标 | 文字说明 | `pass_form` + `restrictions` |
| 库存 | 不显示 | 显示选定日状态 | `availability[date]` |
| 距离 | 不显示 | 显示离 Home 直线英里 | geo + haversine |
| 限制/⚠ | 只一个 ⚠ 角标 | 摊开 blackout/平日/季节/提前/罚款 | `restrictions` |

矩阵格子天生只受前两项影响；其余作用在勾"更详细"后格子内长出的内容。

---

## 七、持卡模型变更：按具体图书馆勾选

客户只知道"我有 Wakefield 和 BPL 的卡"，不知道自己属于哪个联盟。所以：

- 左栏列**具体图书馆**（可多选，按网络分组只为快速定位），勾真实持有的卡。
- **解锁范围逐馆判，不按联盟一刀切**（redesign 发现 2）：一张卡解锁的是 ①本馆 pass + ②那些主动把取 pass 开放给"全联盟/全 MA/不限"的馆；联盟里大量"仅本镇居民"的馆，拿外镇卡取不了。
- 实现：`STATE.selectedNetworks`（联盟集合）改为 `STATE.selectedLibs`（具体 lib id 集合）；`checkL1Card` 逻辑不变（已支持精确 lib id + 网络匹配），只改 UI 选择单位与 `syncSelectedLibs`。

---

## 八、审计

### 8.1 两个高度（有先后）

| 高度 | 在哪审 | 审什么 | 分类 |
|---|---|---|---|
| **大前提**（先做） | 矩阵格子 / 详情的"资格·可用性" | 这张卡 × 这景点**到底该不该可用** | 结论错 → 取错了/取不到 |
| **细节取值**（后做） | 勾"更详细"后展开的各字段 | 优惠 form/value、怎么领、价格等**值对不对** | 值错 → 取错了/取不到 |

顺序：先纠大错 → 再优化自动化 → 最后审细节取值。

### 8.2 ✎ 交互：通过 / 修改

每个值旁一个小笔 ✎，点开两项：

- **通过**：即点即生效，记一条 `status=verified_ok`（信息性，不参与合并）。
- **修改**：打开弹窗 → 选 `correction_kind`（结论错/值错）+ `root_cause`（取错了/取不到）+ **表单改值** → 记 `status=corrected`（`corrected_value` 回流构建）。也可只记 `noted`（备注）。

`root_cause` 含义：
- **取错了** `extraction_error`：原文里有，是抽取/抽象错了 → 后续可靠自动化纠正。
- **取不到** `unobtainable`：原文没说/拿不到 → 只能人工补，以人工结论为最终答案。

### 8.3 审计记录形状

```json
{
  "target": "library:wakefield:card_eligibility",
  "kind": "library | attraction | branch | pass",
  "id": "...",
  "field": "...",
  "status": "verified_ok | corrected | noted",
  "correction_kind": "conclusion_wrong | value_wrong | null",
  "root_cause": "extraction_error | unobtainable | null",
  "corrected_value": <typed value | null>,
  "note": "",
  "audited_at": "ISO8601"
}
```

构建侧只应用 `status==corrected` 的 `corrected_value`（与现有 `apply_overrides` 一致）。

### 8.4 字段 → 表单控件 + ⓘ 原文（按真实数据核实）

控件规则：枚举→下拉、数字→数字框、列表→可增删行、布尔→开关、文本→文本框。ⓘ 先只填原始内容（`source_phrase` 等），没有就显示"无原文记录"。

**A. 图书馆**（改值可回流 ✓）
| 字段 | 控件 | ⓘ |
|---|---|---|
| `card_eligibility` | 下拉：ma_resident / town_resident / town_or_works / network / none / unknown | `eligibility_source_phrase`（常是网页噪声）+ `card_page` 链接 |
| `pass_pickup_default` | 下拉：same_as_card / ma_resident / town_resident / town_cardholder_only / network / walkin_for_nonresidents / none / unknown | `pickup_source_phrase` + `card_page` |

**B. 景点**（改值可回流 ✓）
| 字段 | 控件 | ⓘ |
|---|---|---|
| `visitor_eligibility.residency` | 下拉：ma_resident / town_resident / none / unknown | 无原文（先空）；`website` 链接 |
| `reservation.required` | 下拉：none / timed_entry / walk_in_ok | 无原文（先空） |
| `reservation.booking_url` | 文本(URL) | — |
| `pass_holder_path` | 下拉：promo_code / dedicated_sku / dedicated_url / library_only / unknown | — |
| `prices[]` | 可增删行：受众下拉 + 价格数字 + 年龄段文本 | 每条 `source_phrase` ✓ + `website` |
| `categories` | 多选 | — |

**C. Pass**（本次修复 raw/canonical slug 对齐后可回流）
| 字段 | 控件 | ⓘ |
|---|---|---|
| `coupon.audience_policies[]` | 可增删行：受众文本 + form下拉(free/percent-off/dollar-off/per-person-price/bogo/discount) + value数字 + count数字 + 年龄段文本 | 每条 `source_phrase` ✓ |
| `coupon.capacity` | kind下拉(people/vehicle/ticket/unspecified) + n数字 | `coupon.source_phrase_block` ✓ |
| `pass_form` | 下拉：digital_email / physical_circ / physical_coupon | — |
| `residency_restriction` | restricted下拉(yes/no/unknown) + scope下拉(town/ma/—) | `source` + `evidence`（判断逻辑雏形）✓ |
| `restrictions.*` | weekdays_only开关 / seasonal文本 / advance_booking开关+hours数字 / blackout日期列表 / late_return_penalty文本 | `source_phrase_block` |
| `available_at_branches` | "all" 或多选分馆（仅 BPL/Cambridge/Brookline） | — |

**D. 分馆**（改值可回流 ✓）：name/address 文本、geo 数字。

---

## 九、持久化架构

**单一存储文件**：`data/overrides/audit_overrides.json`（按 target 建键的记录映射），**既是面板实时存储，又是构建管道输入**。

- **读（共享来源）**：面板加载时拉这个文件 → 所有人看同一份。
- **写，按环境分**：
  - **本地**：新增 `scripts/serve_admin.py`，同时托管静态页 + 接收写入（`POST /api/override`），直接落地文件。
  - **Vercel**：新增一个极小 serverless 函数 `/api/override`，GitHub token 存 Vercel **环境变量**（服务端，不泄露），读写 GitHub 上那份文件。审计员**直接打开 Vercel 链接就能审**，无需 token；改动实时写进共享文件；本人随时"下载副本"导出。
- **导出**：降级为可选的"下载当前 overrides 副本"。

> 选型理由：不上 Supabase/KV。一份 GitHub 文件同时承担"持久化 + 共享"，serverless 代写让远端审计员零门槛在平台上审计。

---

## 十、Pass slug 修复

现状：构建侧 pass 用 raw slug 建键（`lib__rawslug`），面板只有 canonical slug（`lib__canonicalslug`），对不上 → pass 改值无法回流。

修复方向（实现阶段定细节）：让面板在加载 passes 时保留 raw slug（或建立 canonical→raw 映射），override target 用与构建侧一致的键，使 pass 的 `corrected_value` 能被 `apply_overrides` 命中。

---

## 十一、明确删除 / 降级

- 删除 4 个 Lens、漏斗模拟器、审计人字段、双导出按钮。
- 不做待审队列、完成度仪表盘、库存审计、直接编辑 raw 数据。

---

## 十二、待定 / 后续

| 项 | 说明 |
|---|---|
| ⓘ 的"AI 判断逻辑"层 | 本期只填原文；发现结论错时再追抽象步骤，届时决定是否补判断逻辑数据 |
| 库存来源刷新 | 仍是构建期快照，不在面板实时抓 |
| 多人并发写冲突 | 个人/小团队使用，暂不做锁；后写覆盖先写 |
