# 「修改数据」反馈表单 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 admin 面板的「修改数据」从「按字段编辑+自动回填」改成「全信息只读铺开 + 反馈收集（根因单选 + 哪块出错多选 + 自由文本）」，反馈存为 `status:"feedback"` JSON、不回填 build、日志可读。

**Architecture:** 纯前端改动（`admin/`）。新增可单测的 `buildFeedbackRecord`（`panel.audit.mjs`）；`panel.js` 替换 `openAuditForm` 为只读渲染 + 反馈表单；矩阵角标 / 审计日志 / 状态筛选加 `feedback` 类型；CSS 重写表单样式。Python build 无需改（`apply_overrides` 只认 `corrected`，`feedback` 天然忽略）。

**Tech Stack:** Vanilla ES modules, `node --test`（无 DOM 框架），Playwright（浏览器人工核对），`scripts/serve_admin.py` 本地起服务。

---

## File Structure

- `admin/assets/panel.audit.mjs` — 新增 `ASPECTS` 常量 + `buildFeedbackRecord()`（可单测）。
- `admin/assets/panel.audit.test.mjs` — `buildFeedbackRecord` 的单测。
- `admin/assets/panel.js` — 替换 `openAuditForm` 及其私有 helper（`zhSelect`/`couponSummaryStr`/`_renderDiscountSubarea` 删除）；新增 `renderCellReadonly` 等只读渲染；改 import；矩阵角标 + 审计日志渲染 + emoji 加 `feedback`；新增模块级 `ASPECT_ZH`。
- `admin/panel.html` — 审计日志状态筛选下拉加 `feedback` 选项。
- `admin/assets/panel.css` — 替换旧 `.af-*` 折扣相关样式为只读展示（`.ro-*`）+ 反馈区（`.af-aspects`/`.af-textarea` 等）；加 `entry-feedback` / `mx-audited-feedback`。

---

## Task 1: `buildFeedbackRecord` + `ASPECTS`（TDD）

**Files:**
- Modify: `admin/assets/panel.audit.mjs`
- Test: `admin/assets/panel.audit.test.mjs`

- [ ] **Step 1: 写失败测试**

在 `admin/assets/panel.audit.test.mjs` 顶部 import 行追加 `buildFeedbackRecord, ASPECTS`：

```javascript
import { auditTarget, buildRecord, controlsFor, buildFeedbackRecord, ASPECTS, CARD_ELIGIBILITY, COUPON_FORM } from "./panel.audit.mjs";
```

在文件末尾追加：

```javascript
test("buildFeedbackRecord: builds a feedback-status record with cell target", () => {
  const r = buildFeedbackRecord({ kind:"pass", id:"acton__ecotarium",
    root_cause:"extraction_error", aspects:["coupon","pass_form"], feedback:"成人是买一送一" });
  assert.equal(r.target, "pass:acton__ecotarium:_feedback");
  assert.equal(r.status, "feedback");
  assert.equal(r.field, "_feedback");
  assert.equal(r.root_cause, "extraction_error");
  assert.deepEqual(r.aspects, ["coupon","pass_form"]);
  assert.equal(r.feedback, "成人是买一送一");
  assert.ok(r.audited_at);
});

test("buildFeedbackRecord: drops unknown aspects, defaults empty", () => {
  const r = buildFeedbackRecord({ kind:"pass", id:"x__y", root_cause:"unobtainable" });
  assert.deepEqual(r.aspects, []);
  assert.equal(r.feedback, "");
});

test("buildFeedbackRecord: rejects invalid root_cause", () => {
  assert.throws(() => buildFeedbackRecord({ kind:"pass", id:"x__y", root_cause:"nope" }));
});

test("buildFeedbackRecord: filters junk aspects against ASPECTS", () => {
  const r = buildFeedbackRecord({ kind:"pass", id:"x__y", root_cause:"unobtainable",
    aspects:["coupon","garbage","other"] });
  assert.deepEqual(r.aspects, ["coupon","other"]);
  assert.ok(ASPECTS.includes("reservation"));
});
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd F:/pj/MuseumPapa/admin/assets && node --test`
Expected: FAIL — `buildFeedbackRecord is not a function` / `ASPECTS` undefined。

- [ ] **Step 3: 实现**

在 `admin/assets/panel.audit.mjs` 末尾（`controlsFor` 之后）追加：

```javascript
export const ASPECTS = ["coupon","pass_form","residency","reservation","attraction","other"];

// Feedback record — NOT machine-applied (build's apply_overrides only honors
// status "corrected"). Collected as JSON for later AI analysis.
export function buildFeedbackRecord({ kind, id, root_cause, aspects = [], feedback = "" }) {
  if (!ROOT_CAUSE.includes(root_cause))
    throw new Error("feedback record requires a valid root_cause");
  return {
    target: auditTarget(kind, id, "_feedback"),
    kind, id, field: "_feedback", status: "feedback",
    root_cause,
    aspects: (aspects || []).filter(a => ASPECTS.includes(a)),
    feedback: feedback || "",
    audited_at: new Date().toISOString(),
  };
}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd F:/pj/MuseumPapa/admin/assets && node --test`
Expected: PASS（原 20 项 + 新 4 项 = 24 项全绿）。

- [ ] **Step 5: 提交**

```bash
git -C F:/pj/MuseumPapa add admin/assets/panel.audit.mjs admin/assets/panel.audit.test.mjs
git -C F:/pj/MuseumPapa commit -m "admin: add buildFeedbackRecord + ASPECTS (feedback-status audit record)"
```

---

## Task 2: `panel.js` — 只读渲染 + 反馈表单替换 openAuditForm

**Files:**
- Modify: `admin/assets/panel.js`（import 行 5；模块级常量；`openAuditForm` 段 ~682-944）

- [ ] **Step 1: 改 import（行 5）**

把：

```javascript
import { auditTarget, buildRecord, controlsFor } from "./panel.audit.mjs";
```

改为：

```javascript
import { buildRecord, buildFeedbackRecord } from "./panel.audit.mjs";
```

- [ ] **Step 2: 删除旧表单 helper + 替换 openAuditForm**

**保留** `const ZH = { … };` 常量对象不动（约 687-739 行，被新只读渲染复用）。删掉**从 `function zhSelect(id, map, cur) {`（约 742 行）到旧 `openAuditForm` 函数结束 `}`（约 944 行）的整段**，包括 `zhSelect`、`couponSummaryStr`、`_renderDiscountSubarea`、旧 `openAuditForm`。

将被删的这段（742-944）替换为以下代码：

```javascript
// 哪块出错 — 多选标签（feedback 表单 + 审计日志共用）
const ASPECT_ZH = {
  coupon: "优惠折扣", pass_form: "取卡方式", residency: "居住限制",
  reservation: "预约要求", attraction: "景点信息", other: "其他",
};

// human-readable value via a ZH map; "—" when empty
function zhVal(map, code) {
  if (code == null || code === "") return "—";
  return map[String(code)] || String(code);
}

// one labelled read-only row
function roRow(label, value) {
  return el("div", { class: "ro-row" },
    el("span", { class: "ro-k" }, label),
    el("span", { class: "ro-v" }, (value == null || value === "") ? "—" : value));
}

// per-audience offer line, e.g. "Adult  50% off  ×2"
function audienceLine(ap) {
  const parts = [ap.audience || "—"];
  if (ap.age_range && (ap.age_range.min != null || ap.age_range.max != null)) {
    const lo = ap.age_range.min, hi = ap.age_range.max;
    parts.push(lo != null && hi != null ? `${lo}–${hi}岁` : hi != null ? `≤${hi}岁` : `≥${lo}岁`);
  }
  parts.push(couponSummary({ audience_policies: [ap] }));
  if (ap.count != null) parts.push(`×${ap.count}`);
  return parts.join("  ");
}

// read-only render of the full cell: pass / library / attraction
function renderCellReadonly(cell, attr) {
  const wrap = el("div", { class: "ro" });
  const p = cell.pass, c = p.coupon;

  wrap.appendChild(el("div", { class: "ro-head" }, "这张 pass"));
  wrap.appendChild(roRow("优惠", couponSummary(c)));
  wrap.appendChild(roRow("容量",
    c?.capacity ? `${c.capacity.kind || "—"}${c.capacity.n != null ? " / " + c.capacity.n : ""}` : "—"));
  const aps = c?.audience_policies || [];
  if (aps.length) {
    const list = el("div", { class: "ro-aud" });
    for (const ap of aps) list.appendChild(el("div", { class: "ro-aud-line" }, audienceLine(ap)));
    wrap.appendChild(el("div", { class: "ro-row" }, el("span", { class: "ro-k" }, "人群明细"), list));
  }
  wrap.appendChild(roRow("取卡方式", zhVal(ZH.pass_form, p.pass_form)));
  const rr = p.residency_restriction;
  wrap.appendChild(roRow("取券居住限制",
    rr ? `${zhVal(ZH.residency_restricted, rr.restricted)}${rr.scope ? " · " + zhVal(ZH.residency_scope, rr.scope) : ""}` : "—"));
  const restr = p.restrictions || {};
  const rbits = [];
  if (restr.weekdays_only) rbits.push("仅工作日");
  if (restr.seasonal) rbits.push("季节性");
  if (restr.advance_booking_required) rbits.push("需提前预约");
  if ((restr.blackout || []).length || (restr.blackout_recurring || []).length) rbits.push("有停用日");
  if (restr.late_return_penalty) rbits.push("逾期罚金");
  wrap.appendChild(roRow("限制", rbits.length ? rbits.join(" · ") : "无"));
  if (p.source_url)
    wrap.appendChild(el("div", { class: "ro-row" },
      el("span", { class: "ro-k" }, "来源"),
      el("a", { class: "ro-v", href: p.source_url, target: "_blank", rel: "noopener" }, "打开 ↗")));

  wrap.appendChild(el("div", { class: "ro-head" }, "图书馆 · " + cell.lib.name));
  wrap.appendChild(roRow("办卡资格", zhVal(ZH.card_eligibility, cell.lib.card_eligibility)));
  wrap.appendChild(roRow("取 pass 资格", zhVal(ZH.pass_pickup_default, cell.lib.pass_pickup_default)));

  wrap.appendChild(el("div", { class: "ro-head" }, "景点 · " + attr.name));
  wrap.appendChild(roRow("访客居住要求", zhVal(ZH.visitor_residency, attr.visitor_eligibility?.residency)));
  wrap.appendChild(roRow("预约要求", zhVal(ZH.reservation_required, attr.reservation?.required)));

  return wrap;
}

// 修改数据 = 只读全信息 + 反馈收集（不回填 build）
function openAuditForm(cell, attr) {
  const form = el("div", { class: "af" });

  form.appendChild(el("div", { class: "af-section-label" }, "当前数据（自动抓取，只读）"));
  form.appendChild(renderCellReadonly(cell, attr));

  form.appendChild(el("div", { class: "af-divider" }));
  form.appendChild(el("div", { class: "af-section-label" }, "这条数据有什么问题？"));

  form.appendChild(el("div", { class: "af-step" }, "原因"));
  form.appendChild(el("div", { class: "af-radio-row" },
    el("label", {}, el("input", { type: "radio", name: "af-cause", value: "extraction_error", checked: "checked" }), " 取错了"),
    el("label", {}, el("input", { type: "radio", name: "af-cause", value: "unobtainable" }), " 取不到")));

  form.appendChild(el("div", { class: "af-step" }, "哪块出错（可多选，可不选）"));
  const aspectRow = el("div", { class: "af-aspects" });
  for (const [code, zh] of Object.entries(ASPECT_ZH))
    aspectRow.appendChild(el("label", { class: "af-aspect" },
      el("input", { type: "checkbox", name: "af-aspect", value: code }), " " + zh));
  form.appendChild(aspectRow);

  form.appendChild(el("div", { class: "af-step" }, "说明"));
  form.appendChild(el("textarea", { id: "af-feedback", class: "af-textarea", rows: "3",
    placeholder: "具体哪里不对、应该是什么…" }));

  const saveBtn = el("button", { class: "btn-tiny primary af-save", onclick: async () => {
    const root_cause = document.querySelector('input[name="af-cause"]:checked').value;
    const aspects = [...document.querySelectorAll('input[name="af-aspect"]:checked')].map(i => i.value);
    const feedback = $("#af-feedback").value.trim();
    if (!feedback && !aspects.length) { alert("请填写说明，或至少选一项「哪块出错」。"); return; }
    const rec = buildFeedbackRecord({
      kind: "pass", id: `${cell.lib.id}__${cell.pass.attraction_rawslug}`,
      root_cause, aspects, feedback,
    });
    await auditPut(rec);
    closeModal();
    renderMatrix();
  } }, "保存反馈");
  form.appendChild(saveBtn);

  openModal(`修改数据：${attr.name} × ${cell.lib.name}`, form);
}
```

- [ ] **Step 3: 起本地服务（若未起）**

Run: `cd F:/pj/MuseumPapa && python scripts/serve_admin.py 8011`（后台运行）
Expected: `admin panel: http://localhost:8011/admin/panel.html`

- [ ] **Step 4: 浏览器核对表单可渲染、保存可写、无报错**

写临时脚本 `F:/pj/MuseumPapa/_tmp_verify.py`：

```python
from playwright.sync_api import sync_playwright
import time
URL = "http://127.0.0.1:8011/admin/panel.html"
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width":900,"height":1000})
    errs=[]; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until="networkidle"); time.sleep(1.0)
    pg.locator(".card-header input[type=checkbox]").first.check(); time.sleep(0.8)
    pg.locator(".mx-cell.mx-click").first.click(); time.sleep(0.4)
    pg.get_by_text("修改数据", exact=True).first.click(); time.sleep(0.4)
    pg.locator(".mx-modal-card").screenshot(path="_tmp_feedback_form.png")
    # fill + save
    pg.locator('input[name="af-aspect"][value="coupon"]').check()
    pg.fill("#af-feedback", "测试反馈：成人其实是买一送一")
    pg.get_by_text("保存反馈", exact=True).click(); time.sleep(0.6)
    print("PAGEERRORS:", errs)
    b.close()
```

Run: `cd F:/pj/MuseumPapa && python _tmp_verify.py`
Expected: `PAGEERRORS: []`，生成 `_tmp_feedback_form.png`。用 Read 看截图，确认三段只读信息（pass/图书馆/景点）+ 原因/哪块/说明 都在。**此时样式可能还很糙（CSS 在 Task 3）**，只验证结构与无报错。

- [ ] **Step 5: 确认写入存储**

Run: `cd F:/pj/MuseumPapa && rtk read data/overrides/audit_overrides.json`
Expected: 出现一条 `..._feedback` 记录，`"status": "feedback"`，`"aspects": ["coupon"]`，`"feedback": "测试反馈：成人其实是买一送一"`。

- [ ] **Step 6: 提交**

```bash
git -C F:/pj/MuseumPapa add admin/assets/panel.js
git -C F:/pj/MuseumPapa commit -m "admin: replace openAuditForm with read-only cell layout + feedback inputs"
```

---

## Task 3: `panel.css` — 替换表单样式（只读展示 + 反馈区）

**Files:**
- Modify: `admin/assets/panel.css`（`/* ── audit form editor` 起的整段 `.af-*`）

- [ ] **Step 1: 整段替换 `.af-*` 样式块**

把 `panel.css` 中从注释 `/* ── audit form editor (openAuditForm) — compact, design-system styled ── */` 起、到 `.af-save { margin-top: 14px; }` 为止的**整段**，替换为：

```css
/* ── 修改数据弹窗：只读全信息展示 + 反馈区 ── */
.af { font-size: 12px; color: var(--ink-2); }
.af-section-label { font-size: 11px; font-weight: 600; letter-spacing: 0.3px;
  color: var(--g); margin: 0 0 6px; }
.af-divider { border-top: 1px solid var(--rule); margin: 14px 0 12px; }

/* read-only cell layout */
.ro { background: var(--paper); border: 1px solid var(--rule); border-radius: 6px;
  padding: 8px 10px; }
.ro-head { font-size: 11px; font-weight: 700; color: var(--ink-2); margin: 10px 0 4px;
  padding-top: 8px; border-top: 1px dashed var(--rule-strong); }
.ro-head:first-child { margin-top: 0; padding-top: 0; border-top: none; }
.ro-row { display: flex; gap: 8px; align-items: baseline; padding: 2px 0; }
.ro-k { flex: 0 0 84px; color: var(--ink-3); font-size: 11px; }
.ro-v { flex: 1; color: var(--ink-2); }
a.ro-v { color: var(--g); text-decoration: none; }
a.ro-v:hover { text-decoration: underline; }
.ro-aud { flex: 1; }
.ro-aud-line { color: var(--ink-2); padding: 1px 0; }

/* feedback inputs */
.af-step { font-weight: 600; font-size: 11px; color: var(--ink-3); margin: 12px 0 5px; }
.af-radio-row { display: flex; gap: 18px; align-items: center; }
.af-radio-row label { display: inline-flex; align-items: center; gap: 5px; flex: none;
  white-space: nowrap; font-size: 13px; color: var(--ink-2); cursor: pointer; }
.af-aspects { display: flex; flex-wrap: wrap; gap: 6px 14px; }
.af-aspect { display: inline-flex; align-items: center; gap: 5px; font-size: 12px;
  color: var(--ink-2); cursor: pointer; }
.af-textarea { width: 100%; box-sizing: border-box; padding: 6px 8px; font-size: 12px;
  border: 1px solid var(--rule); border-radius: 4px; background: var(--white);
  color: var(--ink-2); font-family: inherit; resize: vertical; }
.af-textarea:focus { outline: none; border-color: var(--g); }
.af-save { margin-top: 14px; }
```

- [ ] **Step 2: 浏览器核对样式**

Run: `cd F:/pj/MuseumPapa && python _tmp_verify.py`
Expected: `PAGEERRORS: []`；用 Read 看 `_tmp_feedback_form.png`。核对：三段只读卡片清晰（标签/值对齐）、人群明细逐行、原因两个 radio 并排、哪块出错 tag 横排可换行、说明 textarea 跟设计系统一致、保存按钮在底部。

- [ ] **Step 3: 提交**

```bash
git -C F:/pj/MuseumPapa add admin/assets/panel.css
git -C F:/pj/MuseumPapa commit -m "admin: style 修改数据 feedback form — read-only cell layout + feedback inputs"
```

---

## Task 4: `feedback` 类型接入角标 / 审计日志 / 状态筛选

**Files:**
- Modify: `admin/assets/panel.js`（cell 角标 ~571；审计日志循环 ~1106、emoji ~1127）
- Modify: `admin/panel.html`（状态筛选 ~109）
- Modify: `admin/assets/panel.css`（`mx-audited-*`、`entry-*`）

- [ ] **Step 1: cell 角标加 feedback（panel.js ~571）**

把：

```javascript
    const sym = aStatus === "corrected" ? "✎" : aStatus === "verified_ok" ? "✓" : "📝";
```

改为：

```javascript
    const sym = aStatus === "corrected" ? "✎" : aStatus === "verified_ok" ? "✓" : aStatus === "feedback" ? "💬" : "📝";
```

- [ ] **Step 2: 审计日志可读渲染 feedback（panel.js）**

在 `meta.appendChild(detail);`（约 1109 行）之后、`if (record.status === "corrected" ...` 之前插入：

```javascript
    if (record.status === "feedback") {
      meta.appendChild(el("div", { class: "ale-detail" },
        "原因：" + ({ extraction_error: "取错了", unobtainable: "取不到" }[record.root_cause] || record.root_cause || "—")));
      if ((record.aspects || []).length) {
        const tags = el("div", { class: "ale-aspects" });
        for (const a of record.aspects) tags.appendChild(el("span", { class: "ale-aspect-tag" }, ASPECT_ZH[a] || a));
        meta.appendChild(tags);
      }
      if (record.feedback) meta.appendChild(el("div", { class: "ale-feedback-text" }, "💬 " + record.feedback));
    }
```

- [ ] **Step 3: emoji 加 feedback（panel.js ~1127）**

把：

```javascript
    const emoji = { corrected: "✏️", reviewed: "✅", noted: "📝" }[record.status] || "";
```

改为：

```javascript
    const emoji = { corrected: "✏️", reviewed: "✅", noted: "📝", feedback: "💬" }[record.status] || "";
```

- [ ] **Step 4: 状态筛选下拉加选项（panel.html ~109）**

在 `<option value="noted">📝 noted</option>` 之后加一行：

```html
          <option value="feedback">💬 feedback</option>
```

- [ ] **Step 5: CSS（panel.css）**

在 `.mx-audited-noted { color: #888; }` 之后加：

```css
.mx-audited-feedback { color: #b8860b; }
```

在 `.audit-log-entry.entry-noted     { border-left: 3px solid var(--rule-strong); }` 之后加：

```css
.audit-log-entry.entry-feedback { border-left: 3px solid var(--au); }
.ale-aspects { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 4px; }
.ale-aspect-tag { font-size: 10px; padding: 1px 6px; border-radius: 2px;
  background: var(--au-pale); color: var(--au); border: 1px solid var(--au); }
.ale-feedback-text { font-size: 11px; color: var(--ink-2); margin-top: 3px; line-height: 1.4; }
```

- [ ] **Step 6: 浏览器核对角标 + 日志**

更新 `_tmp_verify.py` 末尾（`b.close()` 之前）追加：

```python
    # reopen,展开审计日志，截图
    pg.locator("#audit-log-toggle").click(); time.sleep(0.3)
    pg.locator("#audit-log-body").screenshot(path="_tmp_audit_log.png")
```

Run: `cd F:/pj/MuseumPapa && python _tmp_verify.py`
Expected: `PAGEERRORS: []`。Read `_tmp_audit_log.png`：确认 feedback 条目显示「原因：取错了」+ 哪块 tag（优惠折扣）+ 「💬 测试反馈…」，左边框琥珀色。Read 矩阵区（可加一张全页截图）确认对应格子出现 💬 角标。

- [ ] **Step 7: 提交**

```bash
git -C F:/pj/MuseumPapa add admin/assets/panel.js admin/panel.html admin/assets/panel.css
git -C F:/pj/MuseumPapa commit -m "admin: surface feedback records in cell badge, audit log, status filter"
```

---

## Task 5: 收尾验证 + 清理

**Files:** 无（验证 + 清理临时文件）

- [ ] **Step 1: 单测全绿**

Run: `cd F:/pj/MuseumPapa/admin/assets && node --test`
Expected: 24 项全 PASS。

- [ ] **Step 2: 清理临时文件 + 测试数据**

撤销验证时写入的测试 feedback 记录（在面板里点该条「撤销」，或直接删 `data/overrides/audit_overrides.json` 里那条），再删临时文件：

Run: `cd F:/pj/MuseumPapa && rm -f _tmp_verify.py _tmp_feedback_form.png _tmp_audit_log.png`
Expected: 无 `_tmp_*`。`git -C F:/pj/MuseumPapa ls-files | grep _tmp_` 为空。

- [ ] **Step 3: 停后台服务**

停掉 `serve_admin.py` 后台进程。

- [ ] **Step 4: 确认工作树干净**

Run: `rtk git -C F:/pj/MuseumPapa status`
Expected: 无未提交的 `admin/` 改动、无 `_tmp_*`。
