# Admin Panel v2 — Plan 2: Matrix View Rewrite

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the 4-Lens tabs + funnel simulator with ONE frozen wide matrix (景点 rows × network-grouped library columns), driven by a left sidebar of per-library card selection + filters + independent display toggles, with rows ranked by best eligibility tier.

**Architecture:** Extract pure, dependency-injected logic (tiering a/b/c/d, residency, availability, row sort, coupon summary) into `admin/assets/panel.logic.mjs`, TDD'd with Node's built-in test runner (the project already uses this pattern in `src/malibbene/testgame/logic.test.mjs`). Convert `panel.js` to an ES module that imports that logic and renders the matrix into the existing `aside.controls` + `main` shell. Audit interactions (✎ 通过/修改, ⓘ) are NOT in this plan — they are Plan 3; this plan renders read-only cells with a placeholder hook where Plan 3 will attach.

**Tech Stack:** Vanilla ES modules, Node `node:test`, CSS `position: sticky` for frozen panes.

This plan covers spec §3 (layout/interaction), §4 (matrix semantics), §5 (filters), §6 (display toggles), §7 (per-library cards). Audit UI (§8) and ⓘ (§8.4) are Plan 3.

Run the panel locally throughout with `python scripts/serve_admin.py 8000` → open `http://localhost:8000/admin/panel.html` (from Plan 1).

---

### Task 1: Pure logic module + tests (`panel.logic.mjs`)

The testable core: tiering, residency, availability, row sort, coupon summary — all pure functions taking explicit dependencies (no global STATE), so Node can test them.

**Files:**
- Create: `admin/assets/panel.logic.mjs`
- Test: `admin/assets/panel.logic.test.mjs`

- [ ] **Step 1: Write the failing tests** — create `admin/assets/panel.logic.test.mjs`:

```js
import { test } from "node:test";
import assert from "node:assert/strict";
import { cardOk, residencyOk, cellTier, availStatus, rowSortKey, bestPolicy, shortSummary } from "./panel.logic.mjs";

const libsById = {
  wakefield: { id: "wakefield", network: "NOBLE", town: "Wakefield", resident_zips: ["01880"] },
  reading:   { id: "reading",   network: "NOBLE", town: "Reading",  resident_zips: ["01867"] },
  bpl:       { id: "bpl",       network: "BPL",   town: "Boston",   resident_zips: ["02118"] },
};
const maZips = new Set(["01880", "01867", "02118"]);

test("cardOk: own id matches", () => {
  assert.equal(cardOk(libsById.wakefield, ["wakefield"], libsById), true);
});
test("cardOk: same network matches", () => {
  assert.equal(cardOk(libsById.reading, ["wakefield"], libsById), true); // both NOBLE
});
test("cardOk: different network fails", () => {
  assert.equal(cardOk(libsById.bpl, ["wakefield"], libsById), false);
});

test("residencyOk: no restriction passes", () => {
  const r = residencyOk({ residency_restriction: { restricted: "no" } }, libsById.wakefield, null, "99999", maZips);
  assert.equal(r.ok, true);
});
test("residencyOk: town scope rejects non-resident zip", () => {
  const pass = { residency_restriction: { restricted: "yes", scope: "town" } };
  const r = residencyOk(pass, libsById.wakefield, null, "01867", maZips);
  assert.equal(r.ok, false);
});
test("residencyOk: ma scope accepts MA zip", () => {
  const pass = { residency_restriction: { restricted: "yes", scope: "ma" } };
  assert.equal(residencyOk(pass, libsById.wakefield, null, "01867", maZips).ok, true);
});
test("residencyOk: unknown passes with warn", () => {
  const r = residencyOk({ residency_restriction: { restricted: "unknown" } }, libsById.wakefield, null, "01880", maZips);
  assert.equal(r.ok, true);
  assert.equal(r.warn, true);
});
test("residencyOk: attraction ma_resident rejects non-MA", () => {
  const r = residencyOk({ residency_restriction: { restricted: "no" } }, libsById.wakefield,
    { visitor_eligibility: { residency: "ma_resident" } }, "99999", maZips);
  assert.equal(r.ok, false);
});

test("cellTier: a/b/c/d matrix", () => {
  assert.equal(cellTier(true, true), "a");
  assert.equal(cellTier(false, true), "b");
  assert.equal(cellTier(true, false), "c");
  assert.equal(cellTier(false, false), "d");
});

test("availStatus: maps states; no date -> none", () => {
  assert.equal(availStatus({ availability: { "2026-05-25": "available" } }, "2026-05-25"), "available");
  assert.equal(availStatus({ availability: { "2026-05-25": "booked" } }, "2026-05-25"), "booked");
  assert.equal(availStatus({ availability: {} }, "2026-05-25"), "unknown");
  assert.equal(availStatus({ availability: {} }, null), "none");
});

test("rowSortKey: best tier + available-first", () => {
  // an 'a' available row sorts before a 'b' row
  assert.deepEqual(rowSortKey([{ tier: "a", avail: "available" }]), [0, 0]);
  assert.deepEqual(rowSortKey([{ tier: "b", avail: "available" }, { tier: "c", avail: "available" }]), [1, 0]);
  assert.deepEqual(rowSortKey([{ tier: "a", avail: "booked" }]), [0, 1]);
  assert.deepEqual(rowSortKey([]), [9, 9]); // empty row sinks
});

test("bestPolicy/shortSummary: pick strongest form", () => {
  const coupon = { audience_policies: [
    { form: "dollar-off", value: 5 },
    { form: "free" },
  ] };
  assert.equal(bestPolicy(coupon).form, "free");
  assert.equal(shortSummary(coupon), "FR");
  assert.equal(shortSummary({ audience_policies: [{ form: "percent-off", value: 50 }] }), "50%");
  assert.equal(shortSummary(null), "");
});
```

- [ ] **Step 2: Run to verify FAIL:**

Run: `node --test admin/assets/panel.logic.test.mjs`
Expected: FAIL — `Cannot find module './panel.logic.mjs'` (module not created yet).

- [ ] **Step 3: Implement** — create `admin/assets/panel.logic.mjs`:

```js
// Pure, dependency-injected logic for the admin matrix. No global STATE, no DOM.
// Mirrors the funnel layer semantics in panel.js / web/src/lib/engine.ts.

export function isMaZip(zip, maZips) { return maZips.has(zip); }

// L1: do the held cards cover this library? (own id, OR a card in the same network)
export function cardOk(lib, heldLibIds, libsById) {
  if (heldLibIds.includes(lib.id)) return true;
  const nets = new Set(heldLibIds.map(id => libsById[id]?.network).filter(Boolean));
  return nets.has(lib.network);
}

// L3 (pass pickup residency) + L4 (attraction visitor residency) combined -> zip eligibility.
// "unknown" counts as ok-with-warn (never hide; flag for audit). Returns {ok, warn, reason}.
export function residencyOk(pass, lib, attr, homeZip, maZips) {
  let warn = false;
  const rr = pass?.residency_restriction;
  if (rr && rr.restricted === "yes") {
    if (rr.scope === "town" && !(lib.resident_zips || []).includes(homeZip))
      return { ok: false, reason: `${lib.town} 仅本镇居民可取` };
    if (rr.scope === "ma" && !isMaZip(homeZip, maZips))
      return { ok: false, reason: "仅 MA 居民可取" };
  } else if (rr && rr.restricted === "unknown") {
    warn = true;
  }
  const ve = attr?.visitor_eligibility;
  if (ve && ve.residency === "ma_resident" && !isMaZip(homeZip, maZips))
    return { ok: false, reason: "景点仅 MA 居民可入" };
  if (ve && (ve.residency === "town_resident" || ve.residency === "unknown")) warn = true;
  return { ok: true, warn };
}

export function cellTier(cardOk_, zipOk_) {
  if (cardOk_ && zipOk_) return "a";
  if (!cardOk_ && zipOk_) return "b";
  if (cardOk_ && !zipOk_) return "c";
  return "d";
}

export function availStatus(pass, iso) {
  if (!iso) return "none";
  const s = pass?.availability?.[iso];
  if (s === "available" || s === "booked" || s === "closed") return s;
  return "unknown";
}

const TIER_RANK = { a: 0, b: 1, c: 2, d: 3 };
// cells: [{tier, avail}] for the passes present in one attraction row. Returns
// [bestTierRank, bestAvailRank] — lower sorts first. Empty row -> [9,9] (sinks).
export function rowSortKey(cells) {
  let bestTier = 9, bestAvail = 9;
  for (const c of cells) {
    const t = TIER_RANK[c.tier] ?? 9;
    const a = c.avail === "available" ? 0 : 1;
    if (t < bestTier || (t === bestTier && a < bestAvail)) { bestTier = t; bestAvail = a; }
  }
  return [bestTier, bestAvail];
}

export const STRENGTH = { free: 6, "percent-off": 5, "dollar-off": 4, "per-person-price": 3, discount: 2, bogo: 1 };
export function bestPolicy(coupon) {
  if (!coupon || !coupon.audience_policies?.length) return null;
  return coupon.audience_policies.slice()
    .sort((a, b) => (STRENGTH[b.form] ?? 0) - (STRENGTH[a.form] ?? 0))[0];
}

// Long human summary (detail rows). Falls back to coupon.summary.
export function couponSummary(coupon) {
  if (!coupon) return "优惠详情未知";
  if (coupon.summary) return coupon.summary;
  const p = bestPolicy(coupon);
  if (!p) return "优惠详情未知";
  switch (p.form) {
    case "free": return "FREE";
    case "percent-off": return `${p.value ?? ""}% off`;
    case "dollar-off": return `$${p.value ?? ""} off`;
    case "per-person-price": return `$${p.value ?? ""}/人`;
    case "bogo": return "买一送一";
    default: return "折扣";
  }
}

// Ultra-short glyph for a matrix cell. "" when no coupon.
export function shortSummary(coupon) {
  const p = bestPolicy(coupon);
  if (!p) return "";
  switch (p.form) {
    case "free": return "FR";
    case "percent-off": return `${p.value ?? ""}%`;
    case "dollar-off": return `$${p.value ?? ""}`;
    case "per-person-price": return `$${p.value ?? ""}`;
    case "bogo": return "B1G1";
    default: return "%";
  }
}
```

- [ ] **Step 4: Run to verify PASS:**

Run: `node --test admin/assets/panel.logic.test.mjs`
Expected: PASS — all tests pass (`# pass <N>`, `# fail 0`).

- [ ] **Step 5: Commit:**

```bash
git -C F:/pj/MuseumPapa add admin/assets/panel.logic.mjs admin/assets/panel.logic.test.mjs
git commit -m "admin: pure matrix logic module (tiering/residency/sort) + node tests"
```
(End the commit message with the `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` trailer — applies to every commit in this plan.)

---

### Task 2: Sidebar — per-library card selection

Spec §7: select specific library cards (grouped by network), not networks. Replace `STATE.selectedNetworks` (Set of network names) with `STATE.selectedLibs` (Set of library ids) as the source of truth; the network header becomes a select-all/none for its members.

**Files:**
- Modify: `admin/assets/panel.js` — `STATE` (lines 25-26, 38-45), `renderCardList` (339-372), `updateLibCount` (374-376), `loadData` default selection (142-143).
- Modify: `admin/panel.html` — the `#lib-list` block hint (lines 18-24).

- [ ] **Step 1: Make `selectedLibs` the source of truth**

In `panel.js` STATE, delete `selectedNetworks` and keep `selectedLibs: new Set()`. Delete `syncSelectedLibs()` entirely. In `loadData` replace lines 142-143:
```js
  // Default: NO cards held (operator ticks the customer's actual cards).
  STATE.selectedLibs = new Set();
```

- [ ] **Step 2: Rewrite `renderCardList`** to render a checkbox per library, grouped by network with a network select-all:

```js
function renderCardList() {
  const wrap = $("#lib-list");
  wrap.innerHTML = "";
  for (const net of STATE.networks) {
    const libs = STATE.libsByNetwork[net];
    const allOn = libs.every(l => STATE.selectedLibs.has(l.id));
    const cardEl = el("div", { class: "card-group" });
    const hdr = el("label", { class: "card-header" },
      el("input", {
        type: "checkbox", ...(allOn ? { checked: "checked" } : {}),
        onchange: (e) => {
          for (const l of libs) {
            if (e.target.checked) STATE.selectedLibs.add(l.id);
            else STATE.selectedLibs.delete(l.id);
          }
          renderCardList(); updateLibCount(); renderMatrix();
        },
      }),
      el("span", { class: "card-name" }, net),
      el("span", { class: "card-count" }, `${libs.length} 馆`),
    );
    cardEl.appendChild(hdr);
    const members = el("div", { class: "card-members" });
    for (const l of libs) {
      members.appendChild(el("label", { class: "card-member" },
        el("input", {
          type: "checkbox", ...(STATE.selectedLibs.has(l.id) ? { checked: "checked" } : {}),
          onchange: (e) => {
            if (e.target.checked) STATE.selectedLibs.add(l.id);
            else STATE.selectedLibs.delete(l.id);
            renderCardList(); updateLibCount(); renderMatrix();
          },
        }),
        el("span", { class: "card-member-name" },
          l.name.replace(/\sPublic Library$|\sLibrary$/, "")),
        eligTag(l.card_eligibility || "unknown"),
      ));
    }
    cardEl.appendChild(members);
    wrap.appendChild(cardEl);
  }
}

function updateLibCount() {
  $("#lib-count").textContent = `${STATE.selectedLibs.size} / ${STATE.libs.length}`;
}
```

- [ ] **Step 3: Update the hint** in `admin/panel.html` (line 23) to:
```html
    <div class="hint" style="margin-bottom:6px">勾选客户实际持有的图书馆卡。能否用某馆的 pass 逐馆判定（同网络不一定通用）。</div>
```

- [ ] **Step 4: Verify manually**

`renderMatrix` does not exist yet (Task 5). For this task, temporarily confirm the sidebar renders without errors by opening the browser console — it will throw `renderMatrix is not defined` on toggle, which is expected until Task 5. Instead verify structurally: the sidebar shows a checkbox per library under each network header, and `#lib-count` reads `0 / <total>` on load.
Run the page via `python scripts/serve_admin.py 8000`; open `http://localhost:8000/admin/panel.html`; confirm per-library checkboxes render and default to unchecked. (Toggling may error until Task 5 — acceptable mid-plan.)

- [ ] **Step 5: Commit:**
```bash
git -C F:/pj/MuseumPapa add admin/assets/panel.js admin/panel.html
git commit -m "admin: per-library card selection (replaces per-network)"
```

---

### Task 3: Filter controls + display toggles in the sidebar

Spec §5 (4 filters) + §6 (independent display toggles). Add an attraction multiselect (default all), keep zip/date, re-purpose "只看可订", and add the display-option checkboxes. Wire everything to `renderMatrix` (built in Task 5).

**Files:**
- Modify: `admin/panel.html` — the `筛选` section (lines 44-53) and add a `显示选项` section.
- Modify: `admin/assets/panel.js` — STATE (add filter/display fields), control wiring in `init`.

- [ ] **Step 1: Replace the `筛选` section** in `admin/panel.html` (lines 44-53) with:

```html
  <section class="ctrl-block">
    <h3>景点筛选 <span class="badge" id="attr-count">0 / 0</span></h3>
    <div class="ctrl-row">
      <button class="btn-tiny" id="btn-attr-all">全选</button>
      <button class="btn-tiny" id="btn-attr-none">清空</button>
    </div>
    <input type="text" id="attr-search" placeholder="搜索景点…" class="al-filter-input" style="width:100%;margin:4px 0">
    <div class="attr-list" id="attr-list"></div>
    <label class="ctrl-check" style="margin-top:6px"><input type="checkbox" id="opt-only-bookable"> 只看可订（隐藏不合规格子）</label>
    <div class="hint">景点是唯一真过滤；卡/Zip 不符只下沉不隐藏。勾"只看可订"后只留 (a) 合规格子。</div>
  </section>

  <section class="ctrl-block">
    <h3>显示选项</h3>
    <label class="ctrl-check"><input type="checkbox" id="d-policies"> 人群条款全展开</label>
    <label class="ctrl-check"><input type="checkbox" id="d-offer"> 优惠具体值</label>
    <label class="ctrl-check"><input type="checkbox" id="d-verdict"> 资格拦截层+原因</label>
    <label class="ctrl-check"><input type="checkbox" id="d-pickup"> 怎么领文字</label>
    <label class="ctrl-check"><input type="checkbox" id="d-avail"> 库存状态</label>
    <label class="ctrl-check"><input type="checkbox" id="d-distance"> 距离</label>
    <label class="ctrl-check"><input type="checkbox" id="d-restrict"> 限制详情</label>
    <div class="hint">每项独立；勾上=更详细，默认=更简洁。</div>
  </section>
```

- [ ] **Step 2: Add STATE fields** in `panel.js` STATE (replace `showOnlyCovered`, `categoryFilter`, `activeLens`):
```js
  selectedAttrs: new Set(),  // attraction slugs to SHOW (default: all)
  attrSearch: "",
  onlyBookable: false,
  display: { policies:false, offer:false, verdict:false, pickup:false, avail:false, distance:false, restrict:false },
```

- [ ] **Step 3: Add `renderAttrList` + default-all** — add this function and call it in `loadData` after indexes:
```js
function renderAttrList() {
  const wrap = $("#attr-list");
  wrap.innerHTML = "";
  const q = STATE.attrSearch.toLowerCase();
  const list = STATE.attractions
    .filter(a => !q || a.name.toLowerCase().includes(q))
    .sort((a, b) => a.name.localeCompare(b.name));
  for (const a of list) {
    wrap.appendChild(el("label", { class: "attr-item" },
      el("input", {
        type: "checkbox", ...(STATE.selectedAttrs.has(a.slug) ? { checked: "checked" } : {}),
        onchange: (e) => {
          if (e.target.checked) STATE.selectedAttrs.add(a.slug);
          else STATE.selectedAttrs.delete(a.slug);
          updateAttrCount(); renderMatrix();
        },
      }),
      el("span", {}, a.name),
    ));
  }
}
function updateAttrCount() {
  $("#attr-count").textContent = `${STATE.selectedAttrs.size} / ${STATE.attractions.length}`;
}
```
In `loadData`, after building `STATE.attrBySlug`, add: `STATE.selectedAttrs = new Set(STATE.attractions.map(a => a.slug));`

- [ ] **Step 4: Wire controls in `init`** — add to the init function (where other listeners are attached):
```js
  $("#btn-attr-all").onclick = () => { STATE.selectedAttrs = new Set(STATE.attractions.map(a=>a.slug)); renderAttrList(); updateAttrCount(); renderMatrix(); };
  $("#btn-attr-none").onclick = () => { STATE.selectedAttrs = new Set(); renderAttrList(); updateAttrCount(); renderMatrix(); };
  $("#attr-search").oninput = (e) => { STATE.attrSearch = e.target.value; renderAttrList(); };
  $("#opt-only-bookable").onchange = (e) => { STATE.onlyBookable = e.target.checked; renderMatrix(); };
  for (const [key, id] of Object.entries({policies:"d-policies",offer:"d-offer",verdict:"d-verdict",pickup:"d-pickup",avail:"d-avail",distance:"d-distance",restrict:"d-restrict"})) {
    $("#"+id).onchange = (e) => { STATE.display[key] = e.target.checked; renderMatrix(); };
  }
  renderAttrList(); updateAttrCount();
```

- [ ] **Step 5: Verify** the controls render (sidebar shows 景点筛选 list with all checked, 显示选项 checkboxes). Toggling may error until Task 5. Commit:
```bash
git -C F:/pj/MuseumPapa add admin/panel.html admin/assets/panel.js
git commit -m "admin: sidebar filters (attraction multiselect, only-bookable) + display toggles"
```

---

### Task 4: Convert panel to ES module + import the logic

`panel.js` must import `panel.logic.mjs`. Make the page load it as a module, and replace the inline pure functions with the imported ones (DRY — single source of truth).

**Files:**
- Modify: `admin/panel.html` (line 184: the `<script>` tag)
- Modify: `admin/assets/panel.js` (top: add import; remove now-duplicated `couponSummary`/`passStrength` helpers, line 219-238)

- [ ] **Step 1: Module script tag** — in `admin/panel.html` change line 184 to:
```html
<script type="module" src="assets/panel.js"></script>
```

- [ ] **Step 2: Import at top of `panel.js`** (after the header comment, before `STATE`):
```js
import { cardOk, residencyOk, cellTier, availStatus, rowSortKey, bestPolicy, couponSummary, shortSummary } from "./panel.logic.mjs";
```

- [ ] **Step 3: Remove duplicated helpers** — delete the inline `couponSummary` (lines 225-238) and the `STRENGTH`/`couponStrength`/`passStrength` block (219-224) from `panel.js`; they now come from the module (`bestPolicy` replaces `passStrength` usage — strength of best policy). If any remaining code calls `passStrength(c)`, replace with `(bestPolicy(c)?.form ? STRENGTH... )` — simplest: keep a tiny local `function passStrength(c){ const p=bestPolicy(c); return p ? ({free:6,"percent-off":5,"dollar-off":4,"per-person-price":3,discount:2,bogo:1}[p.form]??0) : 0; }`.

- [ ] **Step 4: Verify** — `python scripts/serve_admin.py 8000`, open the page, check the browser console shows NO module-load or import errors (a `renderMatrix is not defined` reference is fine until Task 5). Confirm `import` resolves (Network tab shows `panel.logic.mjs` loaded 200).

- [ ] **Step 5: Commit:**
```bash
git -C F:/pj/MuseumPapa add admin/panel.html admin/assets/panel.js
git commit -m "admin: load panel.js as ES module, import shared logic"
```

---

### Task 5: Matrix renderer

The core. Build a single wide table: rows = filtered attractions sorted by `rowSortKey`, columns = libraries grouped by network (prune empty columns, held-card networks first), each cell colored by tier + availability + short summary, expanded per the display toggles. Replace `renderLens` and the lens machinery with `renderMatrix`.

**Files:**
- Modify: `admin/assets/panel.js` — add `buildMatrixModel` + `renderMatrix`; repoint the lens bar / `#lens-content` to call `renderMatrix`.
- Modify: `admin/panel.html` — replace the lens bar + sim bar (lines 72-111) with a single matrix container.

- [ ] **Step 1: Replace `admin/panel.html` lines 72-111** (the `sim-bar`, `lens-bar`, and `lens-content`) with:
```html
    <div class="matrix-container" id="matrix-container">
      <div class="loading-msg">正在加载数据…</div>
    </div>
```

- [ ] **Step 2: Add the model builder** in `panel.js` (uses imported logic):
```js
// Build { columns:[{net,libs:[lib]}], rows:[{attr, cells:{lib_id:{pass,tier,avail,cardOk,zipOk,verdict}}}] }
function buildMatrixModel() {
  const user = getUser();
  const held = user.heldLibraryIds;
  const iso = STATE.visitDate ? STATE.visitDate.toISOString().slice(0, 10) : null;

  // rows: only selected attractions that have at least one pass
  const rows = [];
  for (const attr of STATE.attractions) {
    if (!STATE.selectedAttrs.has(attr.slug)) continue;
    const passes = STATE.passesByAttr[attr.slug] || [];
    if (!passes.length) continue;
    const cells = {};
    const cellList = [];
    for (const pass of passes) {
      const lib = STATE.libsById[pass.library_id];
      if (!lib) continue;
      const ck = cardOk(lib, held, STATE.libsById);
      const rz = residencyOk(pass, lib, attr, STATE.homeZip, STATE.MA_ZIPS);
      const tier = cellTier(ck, rz.ok);
      const avail = availStatus(pass, iso);
      if (STATE.onlyBookable && tier !== "a") continue; // hide non-eligible cells
      const verdict = resolvePass(pass, lib, attr, user, STATE.visitDate);
      const cell = { pass, lib, tier, avail, cardOk: ck, zipOk: rz.ok, warn: rz.warn, verdict };
      cells[lib.id] = cell;
      cellList.push({ tier, avail });
    }
    if (STATE.onlyBookable && !cellList.length) continue; // row emptied by filter
    rows.push({ attr, cells, sortKey: rowSortKey(cellList) });
  }
  rows.sort((a, b) =>
    (a.sortKey[0] - b.sortKey[0]) || (a.sortKey[1] - b.sortKey[1]) || a.attr.name.localeCompare(b.attr.name));

  // columns: networks (held-card networks first), prune libs with no visible cell in any row
  const usedLibIds = new Set();
  for (const r of rows) for (const id of Object.keys(r.cells)) usedLibIds.add(id);
  const heldNets = new Set(held.map(id => STATE.libsById[id]?.network).filter(Boolean));
  const netOrder = STATE.networks.slice().sort((a, b) =>
    (heldNets.has(b) - heldNets.has(a)) || 0);
  const columns = [];
  for (const net of netOrder) {
    const libs = STATE.libsByNetwork[net].filter(l => usedLibIds.has(l.id));
    if (libs.length) columns.push({ net, libs });
  }
  return { columns, rows };
}
```

- [ ] **Step 3: Add the renderer** in `panel.js`:
```js
const TIER_CLASS = { a: "tier-a", b: "tier-b", c: "tier-c", d: "tier-d" };

function renderMatrix() {
  const container = $("#matrix-container");
  const { columns, rows } = buildMatrixModel();
  const flatLibs = columns.flatMap(c => c.libs);
  if (!flatLibs.length || !rows.length) {
    container.innerHTML = "";
    container.appendChild(el("div", { class: "loading-msg" }, "无匹配数据（调整持卡/景点筛选）"));
    return;
  }

  const table = el("table", { class: "matrix-table" });
  // header row 1: network groups
  const thead = el("thead");
  const netTr = el("tr", { class: "mx-net-row" });
  netTr.appendChild(el("th", { class: "mx-corner", rowspan: "2" }, "景点 ＼ 馆"));
  for (const col of columns) {
    netTr.appendChild(el("th", { class: "mx-net", colspan: String(col.libs.length) }, `${col.net} · ${col.libs.length}`));
  }
  thead.appendChild(netTr);
  // header row 2: library names
  const libTr = el("tr", { class: "mx-lib-row" });
  for (const lib of flatLibs) {
    libTr.appendChild(el("th", { class: "mx-lib", title: lib.name },
      lib.name.replace(/\sPublic Library$|\sLibrary$/, "")));
  }
  thead.appendChild(libTr);
  table.appendChild(thead);

  const tbody = el("tbody");
  for (const row of rows) {
    const tr = el("tr");
    tr.appendChild(el("th", { class: "mx-rowhead", title: row.attr.name }, row.attr.name));
    for (const lib of flatLibs) {
      const cell = row.cells[lib.id];
      if (!cell) { tr.appendChild(el("td", { class: "mx-cell mx-empty" })); continue; }
      tr.appendChild(renderCell(cell, row.attr));
    }
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  container.innerHTML = "";
  container.appendChild(table);
}

function renderCell(cell, attr) {
  const d = STATE.display;
  const availCls = cell.avail === "available" ? "av-ok"
    : (cell.avail === "booked" || cell.avail === "closed") ? "av-no"
    : cell.avail === "unknown" ? "av-unk" : "";
  const td = el("td", { class: `mx-cell ${TIER_CLASS[cell.tier]} ${availCls}` });

  // line 1: short offer glyph (or presence dot when 优惠具体值 off)
  const glyph = d.offer ? (couponSummary(cell.pass.coupon)) : (shortSummary(cell.pass.coupon) || "•");
  td.appendChild(el("div", { class: "mx-glyph" }, glyph));

  if (cell.warn) td.appendChild(el("span", { class: "mx-warn", title: "资格未确认" }, "⚠"));
  if (d.avail && cell.avail !== "none") td.appendChild(el("div", { class: "mx-sub" }, cell.avail));
  if (d.verdict && !cell.verdict.eligible) td.appendChild(el("div", { class: "mx-sub mx-block" }, `✗ ${cell.verdict.blockedLayer}`));
  if (d.pickup) td.appendChild(el("div", { class: "mx-sub" }, (PASS_FORM_META[cell.pass.pass_form]?.label) || cell.pass.pass_form));
  if (d.distance && cell.lib.geo && STATE.homeGeo) {
    const mi = haversineMi(STATE.homeGeo, cell.lib.geo);
    if (mi != null) td.appendChild(el("div", { class: "mx-sub" }, `${mi.toFixed(1)} mi`));
  }
  if (d.policies && cell.pass.coupon?.audience_policies?.length > 1) {
    for (const p of cell.pass.coupon.audience_policies)
      td.appendChild(el("div", { class: "mx-sub mx-pol" }, `${p.audience}: ${couponSummary({audience_policies:[p]})}`));
  }
  if (d.restrict && cell.pass.restrictions) {
    const r = cell.pass.restrictions, bits = [];
    if (r.weekdays_only) bits.push("仅平日");
    if (r.seasonal) bits.push("季节性");
    if (r.advance_booking_required) bits.push(`提前${r.advance_booking_hours||""}h`);
    if (r.blackout?.length) bits.push("有blackout");
    if (bits.length) td.appendChild(el("div", { class: "mx-sub mx-restrict" }, bits.join("·")));
  }
  // Plan 3 hook: audit ✎ + ⓘ attach here.
  td.dataset.libId = cell.lib.id;
  td.dataset.attrSlug = attr.slug;
  return td;
}
```

- [ ] **Step 4: Repoint init** — wherever `init()` called `renderLens()` / set up the lens bar, replace with `renderMatrix()`. Update `#home-zip` apply, `#visit-date` change, and geocode handlers to call `renderMatrix()` (they currently call `renderLens()`). Set `STATE.visitDate` from the date input and `STATE.homeZip`/`STATE.homeGeo` as before.

- [ ] **Step 5: Verify manually** — `python scripts/serve_admin.py 8000`, open the page:
  - Matrix renders: attraction rows × library columns grouped by network.
  - Tick a couple of cards (e.g. Wakefield, BPL): cells recolor; rows with an `a` (green) cell float to top.
  - Set a date: cells show availability tint; toggle "库存状态" → text appears.
  - Toggle "只看可订": non-green cells disappear, coverage shrinks.
  - Filter to one attraction via search + 清空/勾选: only that row shows.
  - Toggle display options: cells get richer (policies/verdict/pickup/distance/restrict).
  Report what you observed for each.

- [ ] **Step 6: Commit:**
```bash
git -C F:/pj/MuseumPapa add admin/panel.html admin/assets/panel.js
git commit -m "admin: single frozen wide matrix renderer (tiers, sort, density)"
```

---

### Task 6: CSS — frozen panes, tier colors, density

**Files:**
- Modify: `admin/assets/panel.css`

- [ ] **Step 1: Append matrix styles** to `admin/assets/panel.css`:
```css
/* ── Matrix ── */
.matrix-container { overflow: auto; max-height: calc(100vh - 60px); }
.matrix-table { border-collapse: separate; border-spacing: 0; font-size: 12px; }
.matrix-table th, .matrix-table td { border: 1px solid var(--bd, #d4ddd4); padding: 2px 4px; }
/* frozen first row(s) */
.matrix-table thead th { position: sticky; top: 0; z-index: 3; background: #eaf3ea; }
.mx-net-row th { top: 0; }
.mx-lib-row th { top: 26px; z-index: 3; }
.mx-lib { writing-mode: vertical-rl; transform: rotate(180deg); max-height: 110px; white-space: nowrap; font-weight: 500; }
/* frozen first column */
.mx-corner, .mx-rowhead { position: sticky; left: 0; z-index: 2; background: #f3f8f3; text-align: left; max-width: 180px; }
.mx-corner { z-index: 4; }
.mx-cell { text-align: center; min-width: 34px; vertical-align: top; cursor: default; }
.mx-empty { background: #fafbfa; }
.mx-glyph { font-weight: 600; }
.mx-sub { font-size: 10px; color: #555; }
.mx-block { color: #b00; }
.mx-warn { color: #c80; }
/* tier colors */
.tier-a { background: #d9f2d9; }
.tier-b { background: #fbf3cf; }
.tier-c { background: #fde2cc; }
.tier-d { background: #ececec; color: #999; }
/* availability accents (left border) */
.av-ok  { box-shadow: inset 3px 0 0 #2e9e2e; }
.av-no  { box-shadow: inset 3px 0 0 #c0392b; }
.av-unk { box-shadow: inset 3px 0 0 #d0a000; }
/* sidebar attraction list */
.attr-list { max-height: 220px; overflow:auto; border:1px solid var(--bd,#d4ddd4); border-radius:4px; padding:2px; }
.attr-item { display:flex; gap:6px; align-items:center; font-size:12px; padding:1px 2px; }
```

- [ ] **Step 2: Verify** — reload the page; confirm: first row (network + library headers) stays fixed when scrolling down; first column (attraction names) stays fixed when scrolling right; tier colors render (green/yellow/orange/grey); available cells show a green left edge. Report observations (a screenshot description is fine).

- [ ] **Step 3: Commit:**
```bash
git -C F:/pj/MuseumPapa add admin/assets/panel.css
git commit -m "admin: matrix CSS — frozen first row/col, tier colors, density"
```

---

### Task 7: Remove dead lens/simulator code

**Files:**
- Modify: `admin/assets/panel.js` — delete `buildLensA/B/C/D` (+ `…WithAudit` variants), `buildGroupedTable`, `toggleGroup`, `buildTable`, lens-switching, simulator (`sim-*`) handlers — anything no longer referenced after Task 5. Keep the funnel engine (`resolvePass` etc.), `verdictBadge`, `availBadge`, `eligTag`, `passFormPill` (cells/Plan 3 use them).
- Modify: `admin/panel.html` — remove leftover sim-bar / audit-log markup ONLY IF unused (the audit-log section stays for Plan 3 — leave it).

- [ ] **Step 1: Find references** before deleting:
```bash
cd F:/pj/MuseumPapa
grep -nE "buildLens|buildGroupedTable|toggleGroup|renderLens|activeLens|sim-|buildTable" admin/assets/panel.js
```
Delete each definition whose name has no remaining call site (other than its own definition). Do NOT delete `resolvePass`, `recommend`, `getUser`, badges, `eligTag`, `passFormPill`, `haversineMi`, `fmtMoney`, the audit-log handlers, or anything Plan 3 will need.

- [ ] **Step 2: Verify the page still works** — `node --test admin/assets/panel.logic.test.mjs` (logic still green), then open the page: matrix renders, all Task-5 interactions still work, browser console clean (no `undefined function` errors).

- [ ] **Step 3: Commit:**
```bash
git -C F:/pj/MuseumPapa add admin/assets/panel.js admin/panel.html
git commit -m "admin: remove dead lens + simulator code (matrix is sole view)"
```

---

## Self-Review

**1. Spec coverage:**
- §3 layout (left sidebar all controls + single frozen wide matrix, detail inline via toggles) → Tasks 2,3,5,6. ✓
- §4 matrix semantics (a/b/c/d tier color, availability ▮/▯, row sort by best cell, column prune + held-first) → Task 1 (logic) + Task 5 (model/render). ✓
- §5 four filters + semantics (attractions = only true filter; cards/zip down-sink not hide; date = label only; only-bookable hides non-(a)) → Task 3 + Task 5 `buildMatrixModel`. ✓
- §6 independent display toggles (per dimension, default simple) → Task 3 (controls) + Task 5 `renderCell`. ✓
- §7 per-library card selection, per-library reciprocity → Task 2 + Task 1 `cardOk`. ✓
- Audit (§8) + ⓘ (§8.4) → explicitly Plan 3; Task 5 leaves `td.dataset.libId/attrSlug` hook. ✓

**2. Placeholder scan:** All code steps contain complete code. Task 7 deletes by grep-confirmed reference (not "remove appropriate code" — it names exactly what to keep). The `renderCell` Plan-3 hook is a documented dataset attribute, not a TODO. No "TBD".

**3. Type consistency:** `renderMatrix` is the single re-render entry, called by every control in Tasks 2/3/5. `buildMatrixModel` returns `{columns:[{net,libs}], rows:[{attr,cells,sortKey}]}` consumed by `renderMatrix`. `cells[lib.id] = {pass,lib,tier,avail,cardOk,zipOk,warn,verdict}` matches `renderCell(cell, attr)`. `STATE.selectedLibs`/`selectedAttrs` (Sets) and `STATE.display` (object) are defined in Task 2/3 and read in Task 5. Imported names (`cardOk,residencyOk,cellTier,availStatus,rowSortKey,bestPolicy,couponSummary,shortSummary`) match the Task 1 exports exactly. `passStrength` reference resolved in Task 4 Step 3.
