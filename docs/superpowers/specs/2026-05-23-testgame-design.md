# testgame.html — Pass 预定交互沙盒 设计文档

- 日期：2026-05-23
- 状态：已与用户在对话中确认设计，待 spec 复核后进入 writing-plans
- 产物：项目根目录单文件 `testgame.html`

## 1. 目的

做一个迷你 MVP 小游戏，用**真实抽样数据**感受北岸图书馆 museum-pass 产品的核心交互与逻辑：
用户选定一个 Home Town、勾选自己"持有"的图书馆卡后，页面如实展示每个景点的 Pass，
并根据「是否有可用卡」「是否满足居民资格」给出预定引导。

**铁律：所有博物馆 / Pass / 图书馆数据均从现有 `data/structured/*` 抽取，零编造。**
唯一不来自数据集的是图书馆卡号——卡号本就不属于数据集，且真实 barcode 严禁进仓库，
故卡号改为用户运行时手动填写（见 §6）。

## 2. 形态与技术

- 单文件 `testgame.html`，自包含（内嵌 JS 数据对象 + `<style>` + `<script>`），双击即开，无需服务器、无构建依赖。
- 内嵌数据由一个一次性抽取步骤从 `data/structured/{libraries,attractions,passes}.json` 生成
  （见 §3）。`coupon` 为 `null` 的 pass 如实显示"无折扣信息"，绝不补值。
- 纯前端逻辑，无网络请求（`booking_url` 用 `window.open` 跳转真实预定页）。

## 3. 抽样数据（全部真实）

### 3.1 图书馆（8 家，跨 5 联盟，居民/开放混合）

| lib_id | 馆名 | Town | 联盟 network | 居民政策画像 |
|---|---|---|---|---|
| lynn | Lynn Public Library | Lynn | NOBLE | 多为 Resident Only |
| lynnfield | Lynnfield Public Library | Lynnfield | NOBLE | Open |
| belmont | Belmont Public Library | Belmont | Minuteman | Resident Only |
| acton | Acton Memorial Library | Acton | Minuteman | Open |
| chelmsford | Chelmsford Public Library | Chelmsford | MVLC | Resident Only |
| andover | Memorial Hall Library (Andover) | Andover | MVLC | Open |
| malden | Malden Public Library | Malden | MBLN | Resident Only |
| quincy | Thomas Crane Public Library (Quincy) | Quincy | OCLN | 未标注 (按无限制处理) |

> 馆名以 `libraries.json` 实际 `name` 字段为准。

### 3.2 景点（6 个，均存在于 attractions.json，覆盖最广）

new-england-aquarium、museum-of-science、isabella-stewart-gardner-museum、
zoo-new-england、boston-childrens-museum、peabody-essex-museum。

### 3.3 实际 Pass 网格（8 馆 × 6 景点 = 46/48 cell 有真实 pass）

每个 cell 格式 `residency / coupon.summary`（`-` = 该馆不给该景点供 pass）：

| lib＼attr | aquarium | science | gardner | zoo | childrens | peabody |
|---|---|---|---|---|---|---|
| lynn (NOBLE) | unknown/50% off | - | yes/$10/person | yes/null | yes/Discount | yes/$13.25/person |
| lynnfield (NOBLE) | no/50% off | no/50% off | no/FREE | no/null | no/50% off | no/null |
| belmont (Minuteman) | unknown/50% off | yes/50% off | yes/50% off | yes/null | yes/null | yes/$18/person |
| acton (Minuteman) | unknown/50% off | no/null | no/50% off | no/null | no/$5 off | no/null |
| chelmsford (MVLC) | yes/50% off | yes/50% off | yes/$2/person | yes/null | yes/50% off | yes/$18/person |
| andover (MVLC) | unknown/50% off | no/50% off | no/FREE | no/null | no/50% off | - |
| malden (MBLN) | yes/null | yes/50% off | yes/FREE | yes/null | yes/50% off | yes/null |
| quincy (OCLN) | unknown/$12/person | unknown/null | unknown/FREE | unknown/null | unknown/50% off | unknown/null |

> 该网格为当前 `data/structured/passes.json` 实测结果；抽取步骤须在构建时重新读取，
> 若上游数据变化则以重新抽取为准（本表仅作设计期快照与覆盖性证明）。

### 3.4 Home Town 下拉

选项 = 上述 8 个馆所在镇（Lynn / Lynnfield / Belmont / Acton / Chelmsford / Andover / Malden / Quincy）
**+ 2 个抽样范围外的镇**（Salem、Worcester）。范围外镇用来触发"非居民"状态：
选它时任何 Resident Only 的 pass 都不满足居民资格，而 Open 的 pass 照常可用。

## 4. UI 布局

- **顶部控制区**
  - `Home Town` 下拉（单选，10 个选项，默认未选或选第一个）。
  - 8 个图书馆条目，每条 = 「勾选框（= 假设持有该馆卡）+ 一个可选的卡号输入框」。
- **主体**：每个景点一张卡片。
  - 卡片头：景点真实 `name`、`website` 链接、价格摘要（取 `prices` 里 adult 等）。
  - 卡片内按"提供该景点 pass 的样本馆"逐行列出 **Pass 行**，每行如实展示：
    1. **要求 / 优惠**：`coupon.summary`（如 `$5 off`、`50% off`、`FREE`、`$12/person`），为 null 显示"无折扣信息"。
    2. **图书馆 + 联盟**：馆名 + network 标签（哪些馆 / 哪个联盟能用）。
    3. **居民限制**：`Resident Only`（restricted=yes，标注所在镇）/ `Open` / `Not stated`（unknown）。
  - 卡片底部：一个景点级 `Book` 按钮 + 状态小标签（见 §5）。

## 5. 交互逻辑（景点级聚合）

对每个景点定义：
- `offering` = 样本馆里给该景点供 pass 的馆集合（始终展示）。
- `held` = 用户勾选了的馆 ∩ `offering`（= 用户对该景点持有的可用卡）。
- 某 pass `residentOK` = `restricted != "yes"`（no / unknown 视为无限制） **或** `Home Town == 该馆所在镇`。

聚合状态机：

| 状态 | 判定条件 | 按钮旁标签 | 点 Book 弹窗行为 |
|---|---|---|---|
| 1 完全符合 | 存在 held 且 residentOK 的 pass | （无标签） | 列出可用卡（馆名 + 用户填的卡号）+ Copy；1 张→`Copy and Go`，多张→`Go` + 逐卡 Copy；跳 `booking_url` |
| 2 缺卡 | 无 held 卡，但存在 residentOK 的 pass（居民资格 OK，只差卡） | `Library Pass Needed` | 警告需要某馆的卡，括号列出具体馆 + 联盟；可忽略 → `Go` |
| 3 非居民 | 有 held 卡，但所有 held 的 pass 都是非本镇 Resident Only | `Resident Only` | 警告仅限 {馆所在镇} 居民；列出 held 卡供 Copy；想跳"自凭本事" → `Go` |
| 4 都不符合 | 无 held 卡 **且** 无任何 residentOK 的 pass | `Resident Only` + `Library Pass Needed` | 两条警告并列；仍可忽略 → `Go` |

**`Book` 按钮始终为正常颜色、可点击**（不置灰）。所有状态点击后都进入弹窗，
且**所有状态都允许"忽略警告硬跳"**到 `booking_url`——
大前提是用户填的信息可能不准 / 可能有多重居民身份 / 图书馆卡可能漏录，
平台不硬卡死，只基于用户给的条件做必要警示，以规避平台信息准确度风险。

## 6. 卡号与弹窗复制

- 勾选某馆 = 假设持卡，**所有展示与状态判定照常生效**（卡号非必填）。
- 勾选后出现卡号输入框，用户可手填。仓库内零卡号。
- 弹窗的"可用卡"列表：
  - 列出用户对该景点 held 的卡（馆名 + 用户填的卡号）。
  - 每张卡旁 `Copy` 按钮：填了卡号→可复制；未填→Copy 置灰并提示"未录入卡号"，但 `Go` 照常可跳。
  - 引导按钮：**仅 1 张可用卡 → `Copy and Go`**（复制卡号并跳转）；**多张 → `Go`（只跳转）+ 逐卡手动 Copy**。

## 7. 非目标（Non-Goals）

- 不接任何后端 / API，不写真实预订日志。
- 不做距离 / 地图 / 排序。
- 不存储任何卡号到文件。
- 不做完整 59 馆 / 107 景点，仅本沙盒所需的 8×6 真实子集。
- 不引入构建框架（不用 React/Vite），保持单文件可双击打开。

## 8. 开放问题

无。设计已在对话中逐条与用户确认。
