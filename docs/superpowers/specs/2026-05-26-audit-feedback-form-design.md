# 「修改数据」改为反馈收集表单 — 设计

**日期**：2026-05-26
**范围**：admin 面板（`admin/`）的 cell 纠错流程
**状态**：已与用户确认设计方向，待实现

## 1. 背景与问题

当前 `openAuditForm`（`admin/assets/panel.js`）是一个**按字段编辑**的向导：选根因 → 从下拉里挑一个字段 → 给新值 → 存为 override，由 build 的 `apply_overrides` 自动回填（`out[field] = corrected_value`）。

两个根本问题：

1. **优惠是按人群的**。1033 条 pass 里有 482 条 `coupon.audience_policies` 长度 > 1（如 Adult 50% / Child 50% / Child 0–1岁 免费）。当前表单把优惠拍平成「单一折扣」，表达不了人群差异。
2. **数据结构本身可能就是错的**。把纠错硬塞进固定的结构化字段控件，遇到「连结构都不对」的情况就无法表达。

## 2. 目标 / 非目标

**目标**
- 把一个格子的**全部信息**按其数据结构原样铺开（只读），让审查者看到自动抓取的结果，优惠**按人群逐行**展示。
- 纠错改为**收集反馈**：根因（单选）＋ 哪块出错（多选、可空）＋ 自由文本说明。
- 反馈**不直接改数据、不回填 build**，攒起来供后续 AI 整体分析。

**非目标**
- 不在此表单里做结构化字段的直接编辑 / 自动回填（删除该路径）。
- 不动 `通过审查`（`verified_ok`）流程。
- 不实现 AI 分析本身（仅收集）。
- 不编辑 availability（动态、按日期，只读摘要或略）。

## 3. 设计

### 3.1 弹窗形态（两层，不合并）

点格子 → 现有**详情框**（不变：关键事实 + 源文本 + 预定/复制原文/通过审查/修改数据）。点「修改数据」→ 新的**全信息 + 反馈**弹窗。

> 决策：保持两层而非合并，改动更聚焦，不触碰 `通过审查` 与详情框现有逻辑。

弹窗结构：

```
修改数据：<景点> × <图书馆>
─────────────────────────────────────────
当前数据（自动抓取结果，只读）

▸ 这张 pass
  优惠：<summary>        容量：<kind / n>
    人群明细
      <audience> [<年龄段>]  <形式+数值>  ×<count>
      …
  取卡方式：<pass_form>
  取券居住限制：<restricted / scope>
  限制：<weekdays_only / seasonal / advance_booking … 或「无」>
  来源：<source_url ↗>

▸ 图书馆 · <name>
  办卡资格：<card_eligibility>
  取 pass 资格：<pass_pickup_default>

▸ 景点 · <name>
  访客居住要求：<visitor_eligibility.residency>
  预约要求：<reservation.required>（链接如有）
─────────────────────────────────────────
这条数据有什么问题？

  原因（单选）       ◉ 取错了   ○ 取不到
  哪块出错（可多选，可不选）
     □优惠折扣 □取卡方式 □居住限制 □预约要求 □景点信息 □其他
  说明（自由填写，多行）
     [____________________________________]

                                  [保存反馈]
```

### 3.2 只读展示

- 按数据本身结构分三段：**这张 pass / 图书馆 / 景点**。
- 优惠按 `coupon.audience_policies` **逐行**铺（audience、age_range、form+value、count）。
- 可读标签复用现有 `ZH` 映射；优惠串复用 `couponSummary` / `headlinePolicy`（`panel.logic.mjs`）。
- availability 不铺（动态、体积大）。

### 3.3 反馈区

- **原因**（单选，必选）：`extraction_error`（取错了）/ `unobtainable`（取不到）。
- **哪块出错**（多选，可空）：`coupon` 优惠折扣 / `pass_form` 取卡方式 / `residency` 居住限制 / `reservation` 预约要求 / `attraction` 景点信息 / `other` 其他。
- **说明**：自由文本（多行 textarea）。

### 3.4 记录结构与存储

新增记录状态 `feedback`。记录形如：

```json
{
  "target": "pass:acton__ecotarium:_feedback",
  "kind": "pass",
  "id": "acton__ecotarium",
  "field": "_feedback",
  "status": "feedback",
  "root_cause": "extraction_error",
  "aspects": ["coupon"],
  "feedback": "成人其实是买一送一不是5折",
  "audited_at": "2026-05-26T…Z"
}
```

- `target` 沿用 `kind:id:field`，`field` 固定为 `_feedback`。一个格子存一条，重审覆盖。
- 经现有 `POST /api/overrides`（`scripts/serve_admin.py` → `merge_override`）落到 `data/overrides/audit_overrides.json`。
- build 的 `apply_overrides` 只认 `status=="corrected"`，故 `feedback` 记录**天然被忽略**，不污染产物（无需改 Python，验证即可）。

### 3.4.1 两种受众：人读的日志 vs AI 读的 JSON

同一条记录服务两个去向，**底层都是上面的 JSON**：

- **审计日志（UI，给人看）**：`panel.js` 把 JSON 记录渲染成**可读结构**——`<景点> × <图书馆>` 标题、原因中文（取错了/取不到）、哪块出错中文 tag、说明全文、时间。不暴露原始 JSON 字段名。
- **导出（给 AI 看）**：保持**原样 JSON**。现有「导出」按钮下载 `audit_overrides.json`（`{target: record}`）即为机器/AI 可直接解析的结构，字段保留英文枚举（`extraction_error` / `aspects: ["coupon"]` 等），便于后续 AI 整体分析。导出**不做人读化转换**。

### 3.5 影响面

- **删除** `openAuditForm` 现有按字段编辑逻辑：`FIELDS` 数组、`_renderDiscountSubarea`、`couponSummaryStr`、有折扣/无折扣 toggle 及相关 CSS（`.af-radio-row`、`.af-disc-sub` 等）。
- **新增** 全信息只读渲染 + 反馈表单。
- `panel.audit.mjs`：新增 `ASPECTS` 常量与 `buildFeedbackRecord(...)`；保留 `ROOT_CAUSE`、`ZH` 用于展示；移除不再使用的 `correction_kind` / `CORRECTION_KIND`、`controlsFor`（确认无其他引用后）。
- 矩阵格子角标（`.mx-audited-*`）与审计日志列表（`.audit-log-entry`）**新增 `feedback` 类型**展示。
- `通过审查` 流程不变。

## 4. 测试

- `panel.audit.test.mjs`：为 `buildFeedbackRecord` 增测（target 拼装、status、aspects 透传、root_cause、必填校验）。
- 浏览器验证（playwright，沿用上次手法）：起 `serve_admin.py` → 选馆 → 点格 → 修改数据 → 截图核对只读铺开 + 反馈区 + 保存后角标/日志出现 feedback。
- `node --test`（`admin/assets/`）全绿。

## 5. 已定决策

1. 「哪块出错」选项集：优惠折扣 / 取卡方式 / 居住限制 / 预约要求 / 景点信息 / 其他。
2. 弹窗保持两层（详情框 + 修改数据），不合并。
