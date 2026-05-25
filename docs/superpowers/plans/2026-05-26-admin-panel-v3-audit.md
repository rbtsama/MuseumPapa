# Admin Panel v3 — Plan 3: Form-Based Audit Write + Shared Persistence

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Wire the matrix detail popup's **通过审查** and **修改数据** buttons to write the shared `audit_overrides.json` store (via Plan 1's `/api/overrides`), using a **form editor (never JSON)**, then reflect applied overrides on cells and remove the dead old-audit/lens code.

**Architecture:** A small client store layer (`admin/assets/panel.audit.mjs`) talks to `/api/overrides` (Plan 1's local `serve_admin.py` or Vercel `api/overrides.mjs`), with a localStorage fallback when no endpoint. A pure field→control schema + record builder (in the same `.mjs`, node:test'd) drives a typed form editor. The detail popup's two audit buttons call into this. The legacy localStorage audit system (`auditOpenEditor` JSON editor, `renderLens` + `buildLens*WithAudit` chain, `#auditor-name`, dual export) is removed.

**Tech Stack:** Vanilla ES modules, `node:test`, the `/api/overrides` contract from Plan 1 (GET → `{target:record}`; POST record (must have `target`) → store; POST `{"revoke":target}` → store).

Covers spec §8 (audit). Record shape (Plan 1): `{target, kind, id, field, status, correction_kind, root_cause, corrected_value, note, audited_at}`. Build merges only `status=="corrected"`. **No `audited_by`** (personal/shared use).

Run locally with `python scripts/serve_admin.py 8000`.

---

### Task 1: Audit store client + record builder + field→control map (`panel.audit.mjs`)

The testable core: build a well-formed override record; resolve a field's form-control spec. Pure functions, node:test'd. (Network I/O lives in thin wrappers tested manually.)

**Files:** Create `admin/assets/panel.audit.mjs`, `admin/assets/panel.audit.test.mjs`

- [ ] **Step 1: failing tests** — `admin/assets/panel.audit.test.mjs`:
```js
import { test } from "node:test";
import assert from "node:assert/strict";
import { auditTarget, buildRecord, controlsFor, CARD_ELIGIBILITY, COUPON_FORM } from "./panit.audit.mjs".replace("panit","panel");

test("auditTarget composes kind:id:field", () => {
  assert.equal(auditTarget("library","wakefield","card_eligibility"), "library:wakefield:card_eligibility");
});
test("buildRecord: verified_ok needs no value/root_cause", () => {
  const r = buildRecord({kind:"pass", id:"acton__mfa", field:"_verdict", status:"verified_ok"});
  assert.equal(r.target, "pass:acton__mfa:_verdict");
  assert.equal(r.status, "verified_ok");
  assert.equal(r.corrected_value, null);
  assert.ok(r.audited_at);
});
test("buildRecord: corrected carries value + correction_kind + root_cause", () => {
  const r = buildRecord({kind:"library", id:"wakefield", field:"card_eligibility",
    status:"corrected", correction_kind:"value_wrong", root_cause:"extraction_error",
    corrected_value:"ma_resident", note:"checked site"});
  assert.equal(r.corrected_value, "ma_resident");
  assert.equal(r.correction_kind, "value_wrong");
  assert.equal(r.root_cause, "extraction_error");
});
test("buildRecord: corrected requires a non-undefined value", () => {
  assert.throws(() => buildRecord({kind:"library",id:"x",field:"card_eligibility",status:"corrected"}));
});
test("controlsFor: enum field -> select with options", () => {
  const c = controlsFor("library","card_eligibility","unknown");
  assert.equal(c.control, "select");
  assert.deepEqual(c.options, CARD_ELIGIBILITY);
  assert.equal(c.value, "unknown");
});
test("controlsFor: coupon form -> select; value -> number", () => {
  assert.equal(controlsFor("pass","coupon.form","free").control, "select");
  assert.equal(controlsFor("pass","coupon.value",50).control, "number");
});
test("controlsFor: unknown field -> text", () => {
  assert.equal(controlsFor("attraction","note","").control, "text");
});
```
(Note: the `.replace` import hack above is only to avoid an accidental copy-paste of a wrong name — replace the whole import line with a normal `import { ... } from "./panel.audit.mjs";` listing the same names.)

- [ ] **Step 2: run, expect FAIL** — `node --test admin/assets/panel.audit.test.mjs` → cannot find module.

- [ ] **Step 3: implement** — `admin/assets/panel.audit.mjs`:
```js
// Pure audit-record + form-control logic for the admin panel. No DOM, no network.
export const CARD_ELIGIBILITY = ["ma_resident","town_resident","town_or_works","network","none","unknown"];
export const PASS_PICKUP = ["same_as_card","ma_resident","town_resident","town_cardholder_only","network","walkin_for_nonresidents","none","unknown"];
export const COUPON_FORM = ["free","percent-off","dollar-off","per-person-price","bogo","discount"];
export const CAPACITY_KIND = ["people","vehicle","ticket","unspecified"];
export const VISITOR_RESIDENCY = ["ma_resident","town_resident","none","unknown"];
export const RESERVATION_REQUIRED = ["none","timed_entry","walk_in_ok"];
export const RESIDENCY_RESTRICTED = ["yes","no","unknown"];
export const RESIDENCY_SCOPE = ["town","ma"];
export const PASS_FORM = ["digital_email","physical_coupon","physical_circ"];

export const CORRECTION_KIND = ["conclusion_wrong","value_wrong"]; // 结论错 / 值错
export const ROOT_CAUSE = ["extraction_error","unobtainable"];     // 取错了 / 取不到

export function auditTarget(kind, id, field) { return `${kind}:${id}:${field}`; }

export function buildRecord({ kind, id, field, status, correction_kind = null,
                             root_cause = null, corrected_value, note = "" }) {
  if (status === "corrected" && corrected_value === undefined)
    throw new Error("corrected record requires corrected_value");
  return {
    target: auditTarget(kind, id, field), kind, id, field, status,
    correction_kind: status === "corrected" ? correction_kind : null,
    root_cause: status === "corrected" ? root_cause : null,
    corrected_value: status === "corrected" ? corrected_value : null,
    note, audited_at: new Date().toISOString(),
  };
}

const ENUM = {
  "library:card_eligibility": CARD_ELIGIBILITY,
  "library:pass_pickup_default": PASS_PICKUP,
  "pass:coupon.form": COUPON_FORM,
  "pass:coupon.capacity.kind": CAPACITY_KIND,
  "pass:pass_form": PASS_FORM,
  "pass:residency_restriction.restricted": RESIDENCY_RESTRICTED,
  "pass:residency_restriction.scope": RESIDENCY_SCOPE,
  "attraction:visitor_eligibility.residency": VISITOR_RESIDENCY,
  "attraction:reservation.required": RESERVATION_REQUIRED,
};
const NUMBER = new Set(["pass:coupon.value","pass:coupon.capacity.n","attraction:price"]);

// Returns {control:"select"|"number"|"text", options?, value}
export function controlsFor(kind, field, currentValue) {
  const key = `${kind}:${field}`;
  if (ENUM[key]) return { control: "select", options: ENUM[key], value: currentValue ?? "" };
  if (NUMBER.has(key)) return { control: "number", value: currentValue ?? null };
  return { control: "text", value: currentValue ?? "" };
}
```
(Fix the test's import line to `import { auditTarget, buildRecord, controlsFor, CARD_ELIGIBILITY, COUPON_FORM } from "./panel.audit.mjs";`)

- [ ] **Step 4: run, expect PASS** — `node --test admin/assets/panel.audit.test.mjs` → all pass.

- [ ] **Step 5: commit** — `admin: audit record + field-control logic module (+ node tests)`.

---

### Task 2: Store transport (load/put/revoke) + on-load badges

**Files:** Modify `admin/assets/panel.js`

- [ ] **Step 1** — add transport at top of panel.js (after imports). It GETs the shared store, with localStorage fallback when `/api/overrides` is absent (e.g. opened via file://):
```js
import { auditTarget, buildRecord, controlsFor } from "./panel.audit.mjs";
const AUDIT_LS = "mp_audit_overrides";
async function auditLoadAll() {
  try {
    const r = await fetch("/api/overrides");
    if (r.ok) return await r.json();
  } catch (e) {}
  try { return JSON.parse(localStorage.getItem(AUDIT_LS) || "{}"); } catch (e) { return {}; }
}
async function auditPut(record) {
  STATE.audits[record.target] = record;
  try {
    const r = await fetch("/api/overrides", { method:"POST",
      headers:{"Content-Type":"application/json"}, body: JSON.stringify(record) });
    if (r.ok) { STATE.audits = await r.json(); return; }
  } catch (e) {}
  localStorage.setItem(AUDIT_LS, JSON.stringify(STATE.audits)); // fallback
}
async function auditRevoke(target) {
  delete STATE.audits[target];
  try {
    const r = await fetch("/api/overrides", { method:"POST",
      headers:{"Content-Type":"application/json"}, body: JSON.stringify({revoke:target}) });
    if (r.ok) { STATE.audits = await r.json(); return; }
  } catch (e) {}
  localStorage.setItem(AUDIT_LS, JSON.stringify(STATE.audits));
}
```
- [ ] **Step 2** — add `audits: {}` to `STATE`; in `init()`, `STATE.audits = await auditLoadAll();` before `renderMatrix()`.
- [ ] **Step 3** — in `renderCell`, if any audit record targets this pass (prefix `pass:${cell.lib.id}__${cell.pass.attraction_rawslug}:`), add a small corner badge (✓ verified / ✎ corrected / 📝 noted) class `mx-audited`. CSS: a 8px colored dot top-left.
- [ ] **Step 4: verify** — `node --check admin/assets/panel.js`; via `serve_admin.py`, confirm page still loads and `GET /api/overrides` is hit (Network tab) returning `{}`.
- [ ] **Step 5: commit** — `admin: shared audit store transport + on-load cell badges`.

---

### Task 3: Wire 通过审查 + 修改数据 in the detail popup (form editor)

Replace the Plan-2 placeholder buttons with real behavior.

**Files:** Modify `admin/assets/panel.js` (`openDetailPopup` + new `openAuditForm`)

- [ ] **Step 1** — 通过审查: instant. Replace the placeholder handler with:
```js
foot.appendChild(el("button", { class: "btn-tiny", onclick: async () => {
  const rec = buildRecord({ kind:"pass", id:`${cell.lib.id}__${cell.pass.attraction_rawslug}`,
    field:"_verdict", status:"verified_ok", note:"" });
  await auditPut(rec); planNote("已记录：通过审查 ✓"); renderMatrix();
} }, "通过审查"));
```
- [ ] **Step 2** — 修改数据: opens a form (NOT JSON). Replace the placeholder with `onclick: () => openAuditForm(cell, attr)`. Implement `openAuditForm`:
```js
const AUDITABLE = {  // field label -> {kind, id, field, current}
  // pass-level
  // (build the list from the cell: coupon.form/value, pass_form, residency_restriction.*)
};
function openAuditForm(cell, attr) {
  const p = cell.pass, id = `${cell.lib.id}__${p.attraction_rawslug}`;
  const fields = [
    ["优惠形式", "pass", id, "coupon.form", bestPolicy(p.coupon)?.form],
    ["优惠数值", "pass", id, "coupon.value", bestPolicy(p.coupon)?.value],
    ["取卡方式", "pass", id, "pass_form", p.pass_form],
    ["居住限制", "pass", id, "residency_restriction.restricted", p.residency_restriction?.restricted],
  ];
  const box = el("div", { class: "af" });
  const fieldSel = el("select", { class: "af-field" },
    ...fields.map(([lbl],i) => el("option", { value:String(i) }, lbl)));
  const slot = el("div", { class: "af-slot" });
  const kindRow = el("div", { class: "af-row" },
    el("label", {}, "结论错/值错"),
    el("select", { id:"af-ckind" }, el("option",{value:"value_wrong"},"值错（取错了的值）"),
      el("option",{value:"conclusion_wrong"},"结论错（本不该这样）")));
  const causeRow = el("div", { class: "af-row" },
    el("label", {}, "根因"),
    el("select", { id:"af-cause" }, el("option",{value:"extraction_error"},"取错了（可自动化修）"),
      el("option",{value:"unobtainable"},"取不到（人工为准）")));
  const noteRow = el("input", { id:"af-note", class:"af-note", placeholder:"备注（可选）" });
  let cur = fields[0];
  function renderSlot() {
    const [lbl, kind, fid, field, val] = cur;
    const spec = controlsFor(kind, field, val);
    slot.innerHTML = "";
    let input;
    if (spec.control === "select") input = el("select", { id:"af-val" },
      ...spec.options.map(o => el("option", { value:o, ...(o===String(spec.value)?{selected:"selected"}:{}) }, o)));
    else if (spec.control === "number") input = el("input", { id:"af-val", type:"number", value: spec.value ?? "" });
    else input = el("input", { id:"af-val", type:"text", value: spec.value ?? "" });
    slot.appendChild(el("label", {}, lbl)); slot.appendChild(input);
  }
  fieldSel.addEventListener("change", () => { cur = fields[+fieldSel.value]; renderSlot(); });
  renderSlot();
  const save = el("button", { class:"btn-tiny primary", onclick: async () => {
    const [lbl, kind, fid, field] = cur;
    let v = $("#af-val").value;
    if (controlsFor(kind, field).control === "number") v = v === "" ? null : Number(v);
    const rec = buildRecord({ kind, id:fid, field, status:"corrected",
      correction_kind: $("#af-ckind").value, root_cause: $("#af-cause").value,
      corrected_value: v, note: $("#af-note").value });
    await auditPut(rec); closeModal(); renderMatrix();
  } }, "保存修改");
  box.append(el("label",{},"要改哪个字段"), fieldSel, slot, kindRow, causeRow, noteRow, save);
  openModal(`修改数据 — ${attr.name} × ${cell.lib.name}`, box);
}
```
> NOTE: pass-level corrections now round-trip because Plan 1 emits `attraction_rawslug` and the override key `pass:{lib}__{rawslug}` matches the build. BUT the build's `apply_overrides` sets `out[field]=corrected_value` with `field` being the full dotted path (`coupon.form`) — the build applies it as a top-level key, NOT a nested path. **Implementer: confirm whether nested-path corrections need `apply_overrides` to support dotted paths; if so, extend `apply_overrides` (and add a test) to set nested keys. If out of scope, restrict the editor to top-level fields (`pass_form`, `card_eligibility`, `visitor_eligibility`, `reservation`) and handle coupon via a dedicated coupon-shaped correction.** Resolve this before implementing Step 2.

- [ ] **Step 3: CSS** — `.af-row`, `.af-slot`, `.af-field`, `.af-note`, `.mx-audited` dot.
- [ ] **Step 4: verify (manual)** — via serve_admin: click a cell → 通过审查 records (badge appears, `data/overrides/audit_overrides.json` written); 修改数据 → pick field → typed control (select/number, no JSON) → save → record written, badge appears, survives refresh.
- [ ] **Step 5: commit** — `admin: form-based audit write (通过审查 + 修改数据) wired to shared store`.

---

### Task 4: Single export, drop auditor, remove legacy audit + dead lens chain

**Files:** Modify `admin/panel.html`, `admin/assets/panel.js`

- [ ] **Step 1** — In `panel.html` 审计覆盖 section: remove `#auditor-name`; replace dual export buttons with one `#btn-export-audits` ("导出我的修改"). Keep the audit-log section.
- [ ] **Step 2** — `#btn-export-audits` downloads `STATE.audits` as `audit_overrides.json` (a Blob download).
- [ ] **Step 3** — Remove the legacy localStorage audit system now unused: `auditOpenEditor`/`auditSaveEditor`/`auditOpenPopover`/`makeAuditableCell`/`refreshCellBadge`/`auditExportPerFile`/`auditExportBundle`/`auditGetAuditor` and the `renderLens` + `buildLens*WithAudit` + `buildGroupedTable`/`buildTable`/`toggleGroup`/`passFormPill` chain (grep-confirm no live callers after Tasks 2-3 supersede them). Remove the `#override-editor`/`#override-popover` markup. KEEP `auditRenderLog` (re-point it at `STATE.audits`) for the audit-log section.
- [ ] **Step 4: verify** — `node --check`; `node --test admin/assets/panel.audit.test.mjs admin/assets/panel.logic.test.mjs` green; page loads, audit log lists records, export downloads a valid file. `grep -nE "buildLens|renderLens|auditOpenEditor"` → empty.
- [ ] **Step 5: commit** — `admin: single export, drop auditor, remove legacy audit + dead lens chain`.

---

### Task 5: Build round-trip verification + wrap

- [ ] **Step 1** — Manually author one correction in the panel (e.g. a library `card_eligibility`), confirm it lands in `data/overrides/audit_overrides.json`, then run `python -m pytest tests/test_audit_overrides.py -v` and rebuild (`python scripts/build_all.py` or `build_passes`/`build_libraries`) — confirm the corrected value appears in the structured output and the build's coupon guard still passes.
- [ ] **Step 2** — Full check: `node --test` (both .mjs) green; `python -m pytest -q` (minus the known pre-existing legacy collection errors) shows no NEW failures.
- [ ] **Step 3** — Delete any scratch `data/overrides/audit_overrides.json` test record if not intended to ship.

---

## Self-Review
- §8 audit (✎ 通过/修改, correction_kind 结论错/值错, root_cause 取错了/取不到, NO JSON) → Tasks 1+3. ✓
- §8.3 record shape (no audited_by) → Task 1 `buildRecord`. ✓
- §9 shared persistence (local serve_admin + Vercel, file-backed) → Task 2 transport hits Plan 1's `/api/overrides`. ✓
- single export, no auditor → Task 4. ✓
- ⓘ provenance → already shipped in Plan 2 detail popup (source text + Copy). ✓
- **Open decision flagged in Task 3:** nested dotted-path corrections vs `apply_overrides` top-level merge — resolve before implementing (extend apply_overrides for dotted paths + test, OR restrict editor to top-level fields). This is the one real risk; do not skip it.
- Type consistency: `auditTarget`/`buildRecord`/`controlsFor` signatures shared between `panel.audit.mjs` (def+test) and panel.js (callers). `/api/overrides` contract matches Plan 1.
