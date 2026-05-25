// MuseumPapa Admin Panel — rebuilt on new data shapes + funnel engine
// Edit source under admin/ only. See web/sync-admin.mjs for copy rules.

import { cardOk, residencyOk, cellTier, availStatus, rowSortKey, bestPolicy, couponSummary, shortSummary } from "./panel.logic.mjs";

const DEFAULT_ZIP = "01880";

// ─────────────────────────────────────────────
//  STATE
// ─────────────────────────────────────────────
const STATE = {
  libs: [],
  attractions: [],
  branches: [],
  passes: [],
  townZips: {},       // { towns: { "Wakefield": ["01880"], ... } }
  // indexes
  libsById: {},
  attrBySlug: {},
  passesByAttr: {},   // slug -> Pass[]
  passesByLib: {},    // library_id -> Pass[]
  branchesByLib: {},  // library_id -> Branch[]
  MA_ZIPS: new Set(),
  // derived
  networks: [],
  libsByNetwork: {},
  selectedLibs: new Set(),
  // controls
  homeZip: DEFAULT_ZIP,
  homeGeo: null,
  visitDate: null,     // Date object or null
  showOnlyCovered: false,  // audit tool: show ALL rows (incl. ineligible) by default
  categoryFilter: "",
  activeLens: "A",
  selectedAttrs: new Set(),  // attraction slugs to SHOW (default: all)
  attrSearch: "",
  onlyBookable: false,
  display: { policies:false, offer:false, verdict:false, pickup:false, avail:false, distance:false, restrict:false },
  // group collapse state: net -> bool collapsed
  groupCollapsed: {},
};


// ─────────────────────────────────────────────
//  DOM helpers
// ─────────────────────────────────────────────
const $ = (s) => document.querySelector(s);
function el(tag, attrs = {}, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k === "class") e.className = v;
    else if (k === "html") e.innerHTML = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v);
  }
  for (const kid of kids.flat()) {
    if (kid == null || kid === false) continue;
    e.appendChild(typeof kid === "string" || typeof kid === "number"
      ? document.createTextNode(String(kid)) : kid);
  }
  return e;
}

// Project geo uses `lon` (structured data). zippopotam returns `lng`.
function lng(g) { return g?.lng ?? g?.lon; }
function haversineMi(a, b) {
  if (!a || !b) return null;
  const la = lng(a), lb = lng(b);
  if (a.lat == null || la == null || b.lat == null || lb == null) return null;
  const R = 3958.8, rad = (x) => x * Math.PI / 180;
  const dLat = rad(b.lat - a.lat), dLng = rad(lb - la);
  const s = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(s));
}

function fmtMoney(v) {
  if (v == null) return "—";
  if (v === 0) return "FREE";
  if (Number.isInteger(v)) return `$${v}`;
  return `$${v.toFixed(2)}`;
}

// ─────────────────────────────────────────────
//  DATA LOAD
// ─────────────────────────────────────────────
async function loadData() {
  const fetchJson = async (p) => {
    const r = await fetch(p);
    if (!r.ok) throw new Error(`${p} → ${r.status}`);
    return r.json();
  };
  const [libsD, attrsD, branchesD, passesD, townZipsD] = await Promise.all([
    fetchJson("/data/structured/libraries.json"),
    fetchJson("/data/structured/attractions.json"),
    fetchJson("/data/structured/branches.json"),
    fetchJson("/data/structured/passes.json"),
    fetchJson("/config/town_zips.json"),
  ]);

  STATE.libs = libsD.libraries.slice().sort((a, b) => a.name.localeCompare(b.name));
  STATE.attractions = attrsD.attractions;
  STATE.branches = branchesD.branches;
  STATE.passes = passesD.passes;
  STATE.townZips = townZipsD;

  // Build indexes
  STATE.libsById = {};
  for (const l of STATE.libs) STATE.libsById[l.id] = l;

  STATE.attrBySlug = {};
  for (const a of STATE.attractions) STATE.attrBySlug[a.slug] = a;

  // Default: all attractions selected
  STATE.selectedAttrs = new Set(STATE.attractions.map(a => a.slug));

  STATE.passesByAttr = {};
  STATE.passesByLib = {};
  for (const p of STATE.passes) {
    (STATE.passesByAttr[p.attraction_slug] ||= []).push(p);
    (STATE.passesByLib[p.library_id] ||= []).push(p);
  }

  STATE.branchesByLib = {};
  for (const b of STATE.branches) {
    (STATE.branchesByLib[b.library_id] ||= []).push(b);
  }

  // MA ZIP set
  STATE.MA_ZIPS = new Set(Object.values(townZipsD.towns || {}).flat());

  // Group libs by network
  STATE.libsByNetwork = {};
  for (const l of STATE.libs) {
    const net = l.network || "Unknown";
    (STATE.libsByNetwork[net] ||= []).push(l);
  }
  STATE.networks = Object.keys(STATE.libsByNetwork).sort((a, b) =>
    (STATE.libsByNetwork[b].length - STATE.libsByNetwork[a].length) || a.localeCompare(b));

  // Default: NO cards held (operator ticks the customer's actual cards).
  STATE.selectedLibs = new Set();

  // Perf/ergonomics: collapse every network group by default so the operator
  // expands only the group they care about (avoids rendering ~1000 visible rows).
  STATE.groupCollapsed = {};
  for (const net of STATE.networks) STATE.groupCollapsed[net] = true;
}

// ─────────────────────────────────────────────
//  FUNNEL ENGINE  (mirrors web/src/lib/engine.ts exactly)
// ─────────────────────────────────────────────
function isMaZip(zip) { return STATE.MA_ZIPS.has(zip); }

function checkL1Card(lib, heldLibraryIds) {
  if (heldLibraryIds.includes(lib.id)) return { ok: true };
  const nets = new Set(heldLibraryIds.map(id => STATE.libsById[id]?.network).filter(Boolean));
  if (nets.has(lib.network)) return { ok: true };
  return { ok: false, reason: `no ${lib.network} card` };
}

function checkL3Residency(rr, lib, homeZip) {
  if (!rr || rr.restricted === "no") return { ok: true };
  if (rr.restricted === "unknown") return { ok: true, warn: true, reason: "pickup eligibility unconfirmed" };
  if (rr.scope === "town") return lib.resident_zips.includes(homeZip) ? { ok: true } : { ok: false, reason: `${lib.town} residents only` };
  if (rr.scope === "ma") return isMaZip(homeZip) ? { ok: true } : { ok: false, reason: "MA residents only" };
  return { ok: true, warn: true };
}

function checkL4VisitorResidency(ve, homeZip) {
  if (!ve || ve.residency === "none") return { ok: true };
  if (ve.residency === "unknown") return { ok: true, warn: true, reason: "visitor eligibility unconfirmed" };
  if (ve.residency === "ma_resident") return isMaZip(homeZip) ? { ok: true } : { ok: false, reason: "MA residents only (attraction)" };
  return { ok: true, warn: true, reason: `attraction may be ${ve.scope ?? "town"} residents only` };
}

const WD = ["sundays", "mondays", "tuesdays", "wednesdays", "thursdays", "fridays", "saturdays"];
function checkL8Restrictions(r, date) { // date: Date; USE UTC getters
  if (!r) return { ok: true };
  const m = date.getUTCMonth() + 1, d = date.getUTCDate(), dow = date.getUTCDay();
  for (const b of r.blackout) if (b.month === m && (b.day == null || b.day === d)) return { ok: false, reason: "blackout" };
  if (r.blackout_recurring.includes(WD[dow])) return { ok: false, reason: "not available this weekday" };
  if (r.weekdays_only && (dow === 0 || dow === 6)) return { ok: false, reason: "weekdays only" };
  if (r.seasonal) {
    const { start_month: s, end_month: e } = r.seasonal;
    const inS = s <= e ? (m >= s && m <= e) : (m >= s || m <= e);
    if (!inS) return { ok: false, reason: "out of season" };
  }
  return { ok: true };
}

function checkL10Availability(av, iso) {
  const s = av?.[iso];
  if (s === "available") return { ok: true };
  if (s == null) return { ok: true, warn: true, reason: "availability unknown" };
  return { ok: false, reason: s === "booked" ? "sold out" : "closed/unavailable" };
}

function resolvePass(pass, lib, attr, user, date) {
  const reasons = [], warnings = [];
  const layers = [
    ["L1", checkL1Card(lib, user.heldLibraryIds)],
    ["L3", checkL3Residency(pass.residency_restriction, lib, user.homeZip)],
    ["L4", checkL4VisitorResidency(attr?.visitor_eligibility, user.homeZip)],
  ];
  if (date) {
    layers.push(["L8", checkL8Restrictions(pass.restrictions, date)]);
    const iso = date.toISOString().slice(0, 10);
    layers.push(["L10", checkL10Availability(pass.availability, iso)]);
  }
  for (const [name, r] of layers) {
    if (r.warn && r.reason) warnings.push(r.reason);
    if (!r.ok) return { eligible: false, blockedLayer: name, reasons: [r.reason || name], warnings };
  }
  return { eligible: true, reasons, warnings };
}

// passStrength: local shim used by recommend() and renderSimResults() scoring
function passStrength(c) { const p = bestPolicy(c); return p ? ({free:6,"percent-off":5,"dollar-off":4,"per-person-price":3,discount:2,bogo:1}[p.form]??0) : 0; }
function recommend(slug, user, date) {
  const attr = STATE.attrBySlug[slug];
  if (!attr) return [];
  const scored = [];
  for (const pass of (STATE.passesByAttr[slug] || [])) {
    const lib = STATE.libsById[pass.library_id];
    if (!lib) continue;
    const verdict = resolvePass(pass, lib, attr, user, date);
    let score = passStrength(pass.coupon) * 10;
    if (!verdict.eligible) score -= 1000;
    if (verdict.warnings.length) score -= 5;
    scored.push({ pass, lib, verdict, score });
  }
  scored.sort((a, b) => b.score - a.score);
  const out = [];
  const email = scored.find(r => r.pass.pass_form === "digital_email");
  if (email) out.push(email);
  for (const r of scored) {
    if (out.length >= 4) break;
    if (r.pass.pass_form === "digital_email") continue;
    out.push(r);
  }
  return out.slice(0, 4);
}

// ─────────────────────────────────────────────
//  USER OBJECT
// ─────────────────────────────────────────────
function getUser() {
  return {
    homeZip: STATE.homeZip,
    heldLibraryIds: [...STATE.selectedLibs],
  };
}

// ─────────────────────────────────────────────
//  ELIGIBILITY TAG helpers
// ─────────────────────────────────────────────
const ELIG_LABEL = {
  ma_resident: "MA",
  town_resident: "本镇",
  town_or_works: "本镇",
  network: "网络",
  none: "无限制",
  unknown: "未知",
};
const ELIG_CLASS = {
  ma_resident: "elig-open",
  town_resident: "elig-residents",
  town_or_works: "elig-residents",
  network: "elig-network",
  none: "elig-open",
  unknown: "elig-unknown",
};
function eligTag(v) {
  const lbl = ELIG_LABEL[v] || "未知";
  const cls = ELIG_CLASS[v] || "elig-unknown";
  return el("span", { class: `elig-tag ${cls}` }, lbl);
}

// pass_form display
const PASS_FORM_META = {
  digital_email: { label: "Email", cls: "pill-email" },
  physical_circ: { label: "Loaner", cls: "pill-borrow" },
  physical_coupon: { label: "Coupon", cls: "pill-pickup" },
};
function passFormPill(f) {
  const m = PASS_FORM_META[f] || { label: f || "—", cls: "pill-unknown" };
  return el("span", { class: `pill ${m.cls}` }, m.label);
}

// ─────────────────────────────────────────────
//  VERDICT BADGE
// ─────────────────────────────────────────────
function verdictBadge(verdict) {
  if (!verdict) return el("span", { class: "verdict verdict-blocked" }, "N/A");
  if (verdict.eligible && !verdict.warnings.length) {
    return el("span", { class: "verdict verdict-ok" }, "✓ 合规");
  }
  if (verdict.eligible && verdict.warnings.length) {
    return el("span", { class: "verdict verdict-warn" }, "⚠ 合规(待确认)");
  }
  return el("span", { class: "verdict verdict-blocked" }, `✗ 拦截 ${verdict.blockedLayer || ""}`);
}

// ─────────────────────────────────────────────
//  AVAIL BADGE
// ─────────────────────────────────────────────
function availBadge(pass, iso) {
  if (!iso) return el("span", { class: "avail avail-unknown" }, "未选日期");
  const s = pass.availability?.[iso];
  if (s === "available") return el("span", { class: "avail avail-ok" }, "可预约");
  if (s === "booked") return el("span", { class: "avail avail-booked" }, "已订满");
  if (s === "closed") return el("span", { class: "avail avail-closed" }, "已关闭");
  return el("span", { class: "avail avail-unknown" }, "未知");
}

// ─────────────────────────────────────────────
//  SIDEBAR — card list
// ─────────────────────────────────────────────
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

function renderCategoryFilter() {
  const cats = new Set();
  for (const a of STATE.attractions) (a.categories || []).forEach(c => cats.add(c));
  const sel = $("#opt-category");
  if (sel) for (const c of [...cats].sort()) sel.appendChild(el("option", { value: c }, c));
}

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

// ─────────────────────────────────────────────
//  TABLE BUILDER HELPERS
// ─────────────────────────────────────────────

// Build a <table class="adm-table"> with column defs and row data
// colDefs: [{label, sticky?}]
// rows: elements produced by rowBuilder
function buildTable(colDefs, rowElems) {
  const table = el("table", { class: "adm-table" });
  const thead = el("thead");
  const tr = el("tr");
  for (const col of colDefs) {
    tr.appendChild(el("th", { class: col.sticky ? "col-sticky" : "" }, col.label));
  }
  thead.appendChild(tr);
  table.appendChild(thead);
  const tbody = el("tbody");
  for (const r of rowElems) tbody.appendChild(r);
  table.appendChild(tbody);
  return table;
}

// Network-grouped rows for a flat array of { net, row_tr } items
function buildGroupedTable(colDefs, groupedRows) {
  const table = el("table", { class: "adm-table" });
  const thead = el("thead");
  const tr = el("tr");
  for (const col of colDefs) {
    tr.appendChild(el("th", { class: col.sticky ? "col-sticky" : "" }, col.label));
  }
  thead.appendChild(tr);
  table.appendChild(thead);
  const tbody = el("tbody");
  const netOrder = STATE.networks.filter(n => groupedRows[n]?.length);

  for (const net of netOrder) {
    const rows = groupedRows[net];
    if (!rows || !rows.length) continue;
    const collapsed = STATE.groupCollapsed[net] ?? false;
    // group header row
    const ghTr = el("tr", { class: "group-header", onclick: () => toggleGroup(net, tbody) });
    const ghTd = el("td", { colspan: String(colDefs.length) });
    ghTd.appendChild(document.createTextNode(`${net} · ${rows.length} 条`));
    ghTd.appendChild(el("span", { class: "toggle-icon" }, collapsed ? "+" : "−"));
    ghTr.appendChild(ghTd);
    tbody.appendChild(ghTr);

    for (const rowTr of rows) {
      if (collapsed) rowTr.classList.add("group-row", "collapsed");
      else rowTr.classList.add("group-row");
      rowTr.dataset.net = net;
      tbody.appendChild(rowTr);
    }
  }
  table.appendChild(tbody);
  return table;
}

function toggleGroup(net, tbody) {
  const collapsed = !(STATE.groupCollapsed[net] ?? false);
  STATE.groupCollapsed[net] = collapsed;
  // update rows and icon
  for (const rowTr of tbody.querySelectorAll(`[data-net="${net}"].group-row`)) {
    if (collapsed) rowTr.classList.add("collapsed");
    else rowTr.classList.remove("collapsed");
  }
  // update icon in header
  for (const ghTr of tbody.querySelectorAll(".group-header")) {
    const td = ghTr.querySelector("td");
    if (td && td.textContent.startsWith(net + " ·")) {
      const icon = td.querySelector(".toggle-icon");
      if (icon) icon.textContent = collapsed ? "+" : "−";
    }
  }
}

// ─────────────────────────────────────────────
//  LENS A — 卡覆盖查询
//  Row: one Pass (for selected libs × all attractions)
//  Cols: 图书馆 · 景点 · 我合规吗 · 一句话优惠摘要 · 当日库存
// ─────────────────────────────────────────────
function buildLensA() {
  const user = getUser();
  const date = STATE.visitDate;
  const iso = date ? date.toISOString().slice(0, 10) : null;

  const colDefs = [
    { label: "图书馆", sticky: true },
    { label: "景点" },
    { label: "我合规吗" },
    { label: "一句话优惠摘要" },
    { label: "当日库存" },
    { label: "来源" },
  ];

  // filter: only selected libs; optionally only covered
  const groupedRows = {};
  for (const lib of STATE.libs) {
    if (!STATE.selectedLibs.has(lib.id)) continue;
    const net = lib.network || "Unknown";
    const libPasses = STATE.passesByLib[lib.id] || [];
    for (const pass of libPasses) {
      const attr = STATE.attrBySlug[pass.attraction_slug];
      if (STATE.categoryFilter && !(attr?.categories || []).includes(STATE.categoryFilter)) continue;
      if (STATE.showOnlyCovered && !pass.coupon) continue;
      const verdict = resolvePass(pass, lib, attr, user, date);
      const tr = el("tr");
      // Library col
      const libShort = lib.name.replace(/\sPublic Library$|\sLibrary$/, "");
      tr.appendChild(el("td", { class: "col-sticky" }, libShort));
      // Attraction col
      const attrName = attr ? el("span", { class: "attr-name-serif" }, attr.name) : el("span", {}, pass.attraction_slug);
      tr.appendChild(el("td", {}, attrName));
      // Verdict col
      const vb = verdictBadge(verdict);
      const vCont = el("td", {}, vb);
      if (!verdict.eligible && verdict.reasons?.length) {
        vCont.appendChild(el("div", { class: "cell-reason" }, verdict.reasons.join(" · ")));
      }
      if (verdict.warnings?.length) {
        vCont.appendChild(el("div", { class: "cell-warn-reason" }, "⚠ " + verdict.warnings.join(" · ")));
      }
      tr.appendChild(vCont);
      // Summary col
      const summary = couponSummary(pass.coupon);
      tr.appendChild(el("td", {}, el("span", { class: "cell-summary" }, summary)));
      // Avail col
      tr.appendChild(el("td", {}, availBadge(pass, iso)));
      // Source col
      const srcBtn = pass.source_url
        ? el("button", { class: "book-link", onclick: () => window.open(pass.source_url, "_blank", "noopener,noreferrer") }, "Book →")
        : el("span", { style: "color:var(--ink-3)" }, "—");
      tr.appendChild(el("td", {}, srcBtn));

      (groupedRows[net] ||= []).push(tr);
    }
  }

  return buildGroupedTable(colDefs, groupedRows);
}

// ─────────────────────────────────────────────
//  LENS B — 资格政策审查
//  Row: one Library
//  Cols: 联盟 · 办卡资格 · 取pass资格 · card_page
// ─────────────────────────────────────────────
function buildLensB() {
  const colDefs = [
    { label: "图书馆", sticky: true },
    { label: "联盟(Network)" },
    { label: "办卡资格(card_eligibility)" },
    { label: "取 pass 资格(pass_pickup_default)" },
    { label: "办卡页面" },
  ];

  const groupedRows = {};
  for (const lib of STATE.libs) {
    if (!STATE.selectedLibs.has(lib.id)) continue;
    const net = lib.network || "Unknown";
    const tr = el("tr");
    const libShort = lib.name.replace(/\sPublic Library$|\sLibrary$/, "");
    tr.appendChild(el("td", { class: "col-sticky" }, libShort));
    tr.appendChild(el("td", {}, net));
    // card_eligibility
    const ce = lib.card_eligibility || "unknown";
    tr.appendChild(el("td", {}, eligTag(ce), el("span", { style: "margin-left:6px;font-size:11px;color:var(--ink-3)" }, ce)));
    // pass_pickup_default
    const pp = lib.pass_pickup_default || "unknown";
    tr.appendChild(el("td", {}, el("span", { style: "font-size:12px" }, pp)));
    // card_page
    const link = lib.card_page
      ? el("a", { href: lib.card_page, target: "_blank", class: "lib-name-link" }, "办卡页 ↗")
      : el("span", { style: "color:var(--ink-3)" }, "—");
    tr.appendChild(el("td", {}, link));
    (groupedRows[net] ||= []).push(tr);
  }

  return buildGroupedTable(colDefs, groupedRows);
}

// ─────────────────────────────────────────────
//  LENS C — 优惠细节准确性
//  Row: one Pass
//  Cols: 图书馆 · 景点 · 人群条款(展开) · 容量 · pass_form
// ─────────────────────────────────────────────
function buildLensC() {
  const colDefs = [
    { label: "图书馆", sticky: true },
    { label: "景点" },
    { label: "人群条款(audience_policies)" },
    { label: "容量(capacity)" },
    { label: "pass_form" },
  ];

  const groupedRows = {};
  for (const lib of STATE.libs) {
    if (!STATE.selectedLibs.has(lib.id)) continue;
    const net = lib.network || "Unknown";
    const libPasses = STATE.passesByLib[lib.id] || [];

    for (const pass of libPasses) {
      const attr = STATE.attrBySlug[pass.attraction_slug];
      if (STATE.categoryFilter && !(attr?.categories || []).includes(STATE.categoryFilter)) continue;
      if (STATE.showOnlyCovered && !pass.coupon) continue;

      const tr = el("tr");
      const libShort = lib.name.replace(/\sPublic Library$|\sLibrary$/, "");
      tr.appendChild(el("td", { class: "col-sticky" }, libShort));
      // Attraction
      const attrName = attr ? el("span", { class: "attr-name-serif" }, attr.name) : el("span", {}, pass.attraction_slug);
      tr.appendChild(el("td", {}, attrName));
      // Audience policies — expanded
      const apCell = el("td");
      const policies = pass.coupon?.audience_policies || [];
      if (!policies.length) {
        apCell.appendChild(el("span", { style: "color:var(--ink-3)" }, "—"));
      } else {
        for (const ap of policies) {
          const parts = [];
          if (ap.audience) parts.push(ap.audience);
          const formVal = ap.form + (ap.value != null ? `=${ap.value}` : "");
          parts.push(formVal);
          if (ap.age_range) {
            const { min, max } = ap.age_range;
            if (min != null && max != null) parts.push(`age ${min}-${max}`);
            else if (max != null) parts.push(`age<${max + 1}`);
            else if (min != null) parts.push(`age ${min}+`);
          }
          if (ap.count != null) parts.push(`×${ap.count}`);
          apCell.appendChild(el("div", { class: "ap-row" },
            el("span", { class: "ap-label" }, parts.slice(0, -1).join(" · ") + (parts.length > 1 ? " → " : "")),
            el("span", { class: "ap-val" }, parts[parts.length - 1]),
          ));
        }
      }
      tr.appendChild(apCell);
      // Capacity
      const cap = pass.coupon?.capacity;
      const capStr = cap && cap.n != null ? `${cap.kind} × ${cap.n}` : "—";
      tr.appendChild(el("td", {}, el("span", { class: "cap-label" }, capStr)));
      // pass_form
      tr.appendChild(el("td", {}, passFormPill(pass.pass_form)));
      (groupedRows[net] ||= []).push(tr);
    }
  }

  return buildGroupedTable(colDefs, groupedRows);
}

// ─────────────────────────────────────────────
//  LENS D — 分馆与景点预约
//  Row: one Attraction
//  Cols: 景点名 · 访客residency · 预约要求 · 持卡人通道 · 分馆列表
// ─────────────────────────────────────────────
function buildLensD() {
  const colDefs = [
    { label: "景点", sticky: true },
    { label: "访客居住资格(visitor_eligibility)" },
    { label: "预约要求(reservation)" },
    { label: "持卡人通道" },
    { label: "提供此景点pass的图书馆" },
  ];

  const rows = [];
  for (const attr of STATE.attractions) {
    if (STATE.categoryFilter && !(attr.categories || []).includes(STATE.categoryFilter)) continue;
    // filter: only show attractions covered by selected libs, if showOnlyCovered
    const coveringPasses = (STATE.passesByAttr[attr.slug] || []).filter(p => STATE.selectedLibs.has(p.library_id));
    if (STATE.showOnlyCovered && !coveringPasses.length) continue;

    const tr = el("tr");
    // Attraction col
    tr.appendChild(el("td", { class: "col-sticky" },
      el("span", { class: "attr-name-serif" }, attr.name),
      attr.address?.city ? el("div", { style: "font-size:11px;color:var(--ink-3);margin-top:2px" }, attr.address.city + ", MA") : null,
    ));

    // visitor_eligibility
    const ve = attr.visitor_eligibility;
    const veStr = ve ? ve.residency : "unknown";
    const veNote = ve?.note;
    const veCell = el("td", {},
      el("span", { style: "font-size:12px" }, veStr),
      veNote ? el("div", { style: "font-size:11px;color:var(--ink-3);margin-top:2px" }, veNote) : null,
    );
    tr.appendChild(veCell);

    // reservation
    const resv = attr.reservation;
    let resvBadge;
    if (!resv || resv.required === "none") resvBadge = el("span", { class: "resv-none" }, "无需预约");
    else if (resv.required === "timed_entry") resvBadge = el("span", { class: "resv-required" }, "需定时票");
    else resvBadge = el("span", { class: "resv-walkin" }, "Walk-in OK");
    const resvCell = el("td", {}, resvBadge);
    if (resv?.booking_url) {
      resvCell.appendChild(el("div", { style: "margin-top:4px" },
        el("a", { href: resv.booking_url, target: "_blank", class: "lib-name-link" }, "预约链接 ↗")
      ));
    }
    if (resv?.lead_time_hours) {
      resvCell.appendChild(el("div", { style: "font-size:11px;color:var(--ink-3);margin-top:2px" }, `提前 ${resv.lead_time_hours}h`));
    }
    tr.appendChild(resvCell);

    // pass_holder_url
    const phu = resv?.pass_holder_url;
    const phuCell = phu
      ? el("td", {}, el("a", { href: phu, target: "_blank", class: "lib-name-link" }, "持卡通道 ↗"))
      : el("td", {}, el("span", { style: "color:var(--ink-3)" }, "—"));
    tr.appendChild(phuCell);

    // Libraries providing this attraction, with branch info
    const libCell = el("td");
    if (!coveringPasses.length) {
      libCell.appendChild(el("span", { style: "color:var(--ink-3)" }, "—"));
    } else {
      for (const pass of coveringPasses) {
        const lib = STATE.libsById[pass.library_id];
        if (!lib) continue;
        const libShort = lib.name.replace(/\sPublic Library$|\sLibrary$/, "");
        const branchInfo = pass.available_at_branches === "all"
          ? "所有分馆"
          : (Array.isArray(pass.available_at_branches) ? pass.available_at_branches.join(", ") : String(pass.available_at_branches));
        libCell.appendChild(el("div", { class: "ap-row" },
          el("span", { class: "ap-label" }, libShort + " "),
          el("span", { style: "font-size:11px;color:var(--ink-3)" }, `[${branchInfo}]`),
        ));
      }
    }
    tr.appendChild(libCell);
    rows.push(tr);
  }

  // Lens D is attraction-centric; no network grouping, just a flat table
  return buildTable(colDefs, rows);
}

// ─────────────────────────────────────────────
//  MAIN RENDER DISPATCHER
// ─────────────────────────────────────────────
function renderLens() {
  const container = $("#lens-content");
  container.innerHTML = "";
  let table;
  switch (STATE.activeLens) {
    case "A": table = buildLensAWithAudit(); break;
    case "B": table = buildLensBWithAudit(); break;
    case "C": table = buildLensCWithAudit(); break;
    case "D": table = buildLensDWithAudit(); break;
    default: table = el("div", {}, "Unknown lens");
  }
  container.appendChild(table);
  updateStat();
  // Refresh audit count badge on re-render
  auditUpdateCount();
}

function updateStat() {
  const selCount = STATE.selectedLibs.size;
  let summary = `${selCount} 馆 · ${STATE.attractions.length} 景`;
  if (STATE.homeGeo) summary += ` · ZIP ${STATE.homeZip}`;
  if (STATE.visitDate) summary += ` · ${STATE.visitDate.toISOString().slice(0, 10)}`;
  $("#stat-summary").textContent = summary;
}

// ─────────────────────────────────────────────
//  ZIP geocoding (for distance display only)
// ─────────────────────────────────────────────
async function geocodeZip(zip) {
  const key = `zipgeo:${zip}`;
  const cached = localStorage.getItem(key);
  if (cached) return JSON.parse(cached);
  const r = await fetch(`https://api.zippopotam.us/us/${zip}`);
  if (!r.ok) throw new Error(`zippopotam ${r.status}`);
  const d = await r.json();
  const p = d.places?.[0];
  if (!p) throw new Error("no place");
  const geo = { lat: parseFloat(p.latitude), lng: parseFloat(p.longitude), zip, name: p["place name"] };
  localStorage.setItem(key, JSON.stringify(geo));
  return geo;
}

// ─────────────────────────────────────────────
//  FUNNEL SIMULATOR
// ─────────────────────────────────────────────

/**
 * nextAvailableDay — scan pass.availability forward from `startDate` up to 90 days.
 *
 * Mirrors L10 semantics (checkL10Availability): a missing availability entry is
 * "unknown" (a warn-pass in the live funnel), NOT a hard "unavailable". So:
 *   - If the pass has NO availability data at all (empty map), we DON'T run the
 *     'available' scan — returning a date would be inventing availability, and
 *     returning null falsely claims "no available day". Caller renders an honest
 *     "无库存数据（以馆方为准）" instead. Signalled here via { kind: "no_feed" }.
 *   - If the pass HAS some availability entries, scan forward 90 days for the
 *     first date that is explicitly "available" AND passes L8. Signalled via
 *     { kind: "found", iso } or { kind: "none" } (no available day in window).
 */
function nextAvailableDay(pass, startDate) {
  const WINDOW = 90;
  const av = pass.availability || {};
  // No availability feed at all → don't claim a false negative.
  if (!av || Object.keys(av).length === 0) return { kind: "no_feed" };
  // start scanning from startDate itself (inclusive)
  const cur = new Date(startDate.getTime());
  for (let i = 0; i < WINDOW; i++) {
    const iso = cur.toISOString().slice(0, 10);
    if (av[iso] === "available") {
      const l8 = checkL8Restrictions(pass.restrictions, cur);
      if (l8.ok) return { kind: "found", iso };
    }
    cur.setUTCDate(cur.getUTCDate() + 1);
  }
  return { kind: "none" };
}

function simGetUser() {
  const zipInput = (document.getElementById("sim-zip")?.value || "").trim();
  const cardsInput = (document.getElementById("sim-cards")?.value || "").trim();
  const homeZip = /^\d{5}$/.test(zipInput) ? zipInput : STATE.homeZip;
  let heldLibraryIds;
  if (cardsInput) {
    heldLibraryIds = cardsInput.split(",").map(s => s.trim()).filter(Boolean);
  } else {
    heldLibraryIds = [...STATE.selectedLibs];
  }
  return { homeZip, heldLibraryIds };
}

function simGetDate() {
  const v = document.getElementById("sim-date")?.value;
  return v ? new Date(v + "T00:00:00Z") : STATE.visitDate;
}

function renderSimResults() {
  const resultsEl = document.getElementById("sim-results");
  if (!resultsEl) return;
  resultsEl.innerHTML = "";

  const slugSel = document.getElementById("sim-attr");
  const slug = slugSel?.value;
  if (!slug) {
    resultsEl.appendChild(el("div", { class: "sim-no-passes" }, "请先选择景点"));
    return;
  }

  const attr = STATE.attrBySlug[slug];
  const passes = STATE.passesByAttr[slug] || [];
  const user = simGetUser();
  const date = simGetDate();

  if (!passes.length) {
    resultsEl.appendChild(el("div", { class: "sim-no-passes" }, "该景点暂无 pass 数据"));
    return;
  }

  // attr header
  resultsEl.appendChild(el("div", { class: "sim-attr-name" },
    attr ? attr.name : slug,
    el("span", { style: "font-size:11px;font-weight:400;font-family:inherit;color:var(--ink-3);margin-left:8px" },
      `${passes.length} 条 pass · ZIP ${user.homeZip} · ${date ? date.toISOString().slice(0,10) : "未选日期"}`
    )
  ));

  // Score all passes
  const rows = [];
  for (const pass of passes) {
    const lib = STATE.libsById[pass.library_id];
    if (!lib) continue;
    const verdict = resolvePass(pass, lib, attr, user, date);
    let score = passStrength(pass.coupon) * 10;
    if (!verdict.eligible) score -= 1000;
    if (verdict.warnings.length) score -= 5;
    rows.push({ pass, lib, verdict, score });
  }
  rows.sort((a, b) => b.score - a.score);

  // Render
  const eligRows = rows.filter(r => r.verdict.eligible);
  const blockedRows = rows.filter(r => !r.verdict.eligible);

  function renderPassCard(r) {
    const { pass, lib, verdict } = r;
    const libShort = lib.name.replace(/\sPublic Library$|\sLibrary$/, "");
    const isTimeBlock = !verdict.eligible && (verdict.blockedLayer === "L8" || verdict.blockedLayer === "L10");

    let cardClass = "sim-pass-card";
    if (verdict.eligible && verdict.warnings.length) cardClass += " sim-warn";
    else if (verdict.eligible) cardClass += " sim-eligible";
    else cardClass += " sim-blocked";

    const card = el("div", { class: cardClass });

    // left: meta
    const metaEl = el("div", { class: "sim-pass-meta" },
      el("span", { class: "sim-pass-lib" }, libShort),
      el("span", { class: "sim-pass-form" }, passFormPill(pass.pass_form)),
      pass.coupon ? el("span", { class: "sim-pass-coupon" }, couponSummary(pass.coupon)) : null,
    );

    if (!verdict.eligible && verdict.reasons?.length) {
      metaEl.appendChild(el("div", { class: "sim-pass-reason" },
        `${verdict.blockedLayer}: ${verdict.reasons.join(" · ")}`
      ));
    }
    if (verdict.warnings?.length) {
      metaEl.appendChild(el("div", { class: "sim-pass-warn" }, "⚠ " + verdict.warnings.join(" · ")));
    }

    // next-available-day for time-layer blocks
    if (isTimeBlock && date) {
      const next = nextAvailableDay(pass, date);
      let nextEl;
      if (next.kind === "found") {
        nextEl = el("div", { class: "sim-next-avail" }, `下一可用日: ${next.iso}`);
      } else if (next.kind === "no_feed") {
        // Honest: no availability feed — don't claim a false negative.
        nextEl = el("div", { class: "sim-next-avail", style: "color:var(--ink-3)" },
          "无库存数据（以馆方为准）");
      } else {
        nextEl = el("div", { class: "sim-next-avail", style: "color:var(--rd);background:var(--rd-pale);border-color:var(--rd)" },
          "未来 90 天内无可用日");
      }
      metaEl.appendChild(nextEl);
    }

    card.appendChild(metaEl);

    // right: verdict badge
    const vb = verdict.eligible
      ? (verdict.warnings.length
          ? el("span", { class: "verdict verdict-warn" }, "⚠ 可预订(待确认)")
          : el("span", { class: "verdict verdict-ok" }, "✓ 可预订"))
      : el("span", { class: "verdict verdict-blocked" }, `✗ 拦截 ${verdict.blockedLayer || ""}`);
    card.appendChild(el("div", { class: "sim-pass-verdict" }, vb));

    return card;
  }

  if (eligRows.length) {
    resultsEl.appendChild(el("div", { class: "sim-eligible-hdr" }, `✓ 可预订 (${eligRows.length})`));
    for (const r of eligRows) resultsEl.appendChild(renderPassCard(r));
  }
  if (blockedRows.length) {
    resultsEl.appendChild(el("div", { class: "sim-blocked-hdr" }, `✗ 被拦截 (${blockedRows.length})`));
    for (const r of blockedRows) resultsEl.appendChild(renderPassCard(r));
  }
}

function initSimulator() {
  // populate attraction select
  const sel = document.getElementById("sim-attr");
  if (!sel) return;
  const sorted = STATE.attractions.slice().sort((a, b) => a.name.localeCompare(b.name));
  for (const attr of sorted) {
    sel.appendChild(el("option", { value: attr.slug }, attr.name));
  }

  // default date = same as main panel
  const simDate = document.getElementById("sim-date");
  if (simDate && STATE.visitDate) {
    simDate.value = STATE.visitDate.toISOString().slice(0, 10);
  } else if (simDate) {
    simDate.value = new Date().toLocaleDateString("en-CA");
  }

  // toggle collapse
  const toggle = document.getElementById("sim-toggle");
  const body = document.getElementById("sim-body");
  const chevron = document.getElementById("sim-chevron");
  const subtitle = document.getElementById("sim-subtitle");

  function toggleSim() {
    const isOpen = !body.hidden;
    body.hidden = isOpen;
    chevron.classList.toggle("open", !isOpen);
    toggle.setAttribute("aria-expanded", String(!isOpen));
    if (!isOpen) {
      subtitle.textContent = '正在运行…请点击「运行模拟」';
    } else {
      subtitle.textContent = "选择景点，逐层验证每张 pass 的可用性";
    }
  }
  toggle.addEventListener("click", toggleSim);
  toggle.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggleSim(); } });

  // run button
  document.getElementById("sim-run").addEventListener("click", () => {
    renderSimResults();
  });

  // also run on attraction change (auto-run if simulator is open)
  sel.addEventListener("change", () => {
    if (!body.hidden) renderSimResults();
  });
}

// ─────────────────────────────────────────────
//  MATRIX MODEL + RENDERER
// ─────────────────────────────────────────────

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

const TIER_CLASS = { a: "tier-a", b: "tier-b", c: "tier-c", d: "tier-d" };

function renderMatrix() {
  const container = $("#matrix-container");
  if (!container) return;
  const { columns, rows } = buildMatrixModel();
  const flatLibs = columns.flatMap(c => c.libs);
  if (!flatLibs.length || !rows.length) {
    container.innerHTML = "";
    container.appendChild(el("div", { class: "loading-msg" }, "No matching data (adjust cards / attraction filter)"));
    return;
  }

  const table = el("table", { class: "matrix-table" });
  // header row 1: network groups
  const thead = el("thead");
  const netTr = el("tr", { class: "mx-net-row" });
  netTr.appendChild(el("th", { class: "mx-corner", rowspan: "2" }, "Attraction ＼ Library"));
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

  if (cell.warn) td.appendChild(el("span", { class: "mx-warn", title: "eligibility not confirmed (residency unknown in our data)" }, "⚠"));
  if (d.avail && cell.avail !== "none") td.appendChild(el("div", { class: "mx-sub" }, cell.avail));
  if (d.verdict && !cell.verdict.eligible) td.appendChild(el("div", { class: "mx-sub mx-block", title: `blocked at ${cell.verdict.blockedLayer}` }, `✗ ${cell.verdict.reasons[0] || cell.verdict.blockedLayer}`));
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
    if (r.weekdays_only) bits.push("weekdays");
    if (r.seasonal) bits.push("seasonal");
    if (r.advance_booking_required) bits.push(`${r.advance_booking_hours||""}h ahead`);
    if (r.blackout?.length) bits.push("blackout");
    if (bits.length) td.appendChild(el("div", { class: "mx-sub mx-restrict" }, bits.join("·")));
  }
  // Plan 3 hook: audit ✎ + ⓘ attach here.
  td.dataset.libId = cell.lib.id;
  td.dataset.attrSlug = attr.slug;
  return td;
}

// ─────────────────────────────────────────────
//  INIT & WIRE-UP
// ─────────────────────────────────────────────
async function init() {
  // Set default date to today (local)
  const todayStr = new Date().toLocaleDateString("en-CA"); // YYYY-MM-DD
  const dateInput = $("#visit-date");
  dateInput.value = todayStr;
  STATE.visitDate = new Date(todayStr + "T00:00:00Z");

  await loadData();
  renderCardList();
  updateLibCount();
  renderCategoryFilter();
  renderAttrList(); updateAttrCount();
  renderMatrix();
  initAuditSystem();

  // Attr filter controls
  $("#btn-attr-all").onclick = () => { STATE.selectedAttrs = new Set(STATE.attractions.map(a=>a.slug)); renderAttrList(); updateAttrCount(); renderMatrix(); };
  $("#btn-attr-none").onclick = () => { STATE.selectedAttrs = new Set(); renderAttrList(); updateAttrCount(); renderMatrix(); };
  $("#attr-search").oninput = (e) => { STATE.attrSearch = e.target.value; renderAttrList(); };
  $("#opt-only-bookable").onchange = (e) => { STATE.onlyBookable = e.target.checked; renderMatrix(); };
  for (const [key, id] of Object.entries({policies:"d-policies",offer:"d-offer",verdict:"d-verdict",pickup:"d-pickup",avail:"d-avail",distance:"d-distance",restrict:"d-restrict"})) {
    $("#"+id).onchange = (e) => { STATE.display[key] = e.target.checked; renderMatrix(); };
  }

  // All / None (card selection)
  $("#btn-all").addEventListener("click", () => {
    for (const l of STATE.libs) STATE.selectedLibs.add(l.id);
    renderCardList(); updateLibCount(); renderMatrix();
  });
  $("#btn-none").addEventListener("click", () => {
    STATE.selectedLibs.clear();
    renderCardList(); updateLibCount(); renderMatrix();
  });

  // Date
  dateInput.addEventListener("change", (e) => {
    const v = e.target.value;
    STATE.visitDate = v ? new Date(v + "T00:00:00Z") : null;
    renderMatrix();
  });

  // ZIP
  async function applyZip() {
    const input = $("#home-zip");
    const hint = $("#zip-hint");
    let zip = (input.value || "").trim();
    if (!/^\d{5}$/.test(zip)) {
      zip = DEFAULT_ZIP;
      input.value = DEFAULT_ZIP;
      hint.textContent = `ZIP 格式不对；已恢复默认 ${DEFAULT_ZIP}。`;
      hint.className = "hint warn";
    } else {
      hint.textContent = "解析中…"; hint.className = "hint";
    }
    STATE.homeZip = zip;
    try {
      STATE.homeGeo = await geocodeZip(zip);
      hint.textContent = `${STATE.homeGeo.name} (${STATE.homeGeo.lat.toFixed(3)}, ${STATE.homeGeo.lng.toFixed(3)})`;
      hint.className = "hint ok";
    } catch (e) {
      STATE.homeGeo = null;
      hint.textContent = `位置解析失败: ${e.message}（居住资格检查仍有效）`;
      hint.className = "hint warn";
    }
    renderMatrix();
  }
  $("#btn-geocode").addEventListener("click", applyZip);
  $("#home-zip").addEventListener("keydown", (e) => { if (e.key === "Enter") applyZip(); });
  $("#home-zip").addEventListener("blur", () => {
    if (!($("#home-zip").value || "").trim()) $("#home-zip").value = DEFAULT_ZIP;
  });

  // Auto-apply default ZIP on load
  applyZip();
}

// ─────────────────────────────────────────────
//  AUDIT OVERRIDE SYSTEM
//  localStorage key: mp_audit_overrides
//  Record shape:
//    { target, kind, id, field, status, corrected_value, note, audited_at, audited_by }
//  Directory layout produced for export:
//    libraries/<id>/<field>.json
//    attractions/<slug>/<field>.json
//    branches/<lib>__<branch>/<field>.json
//    passes/<lib>__<slug>/<field>.json  (informational only; corrected NOT applied)
// ─────────────────────────────────────────────

const AUDIT_LS_KEY = "mp_audit_overrides";

function auditLoad() {
  try { return JSON.parse(localStorage.getItem(AUDIT_LS_KEY) || "{}"); }
  catch { return {}; }
}
function auditSave(map) {
  localStorage.setItem(AUDIT_LS_KEY, JSON.stringify(map));
  auditUpdateCount();
  auditRenderLog();
}
function auditGet(target) { return auditLoad()[target] || null; }
function auditSet(record) {
  const map = auditLoad();
  map[record.target] = record;
  auditSave(map);
}
function auditDelete(target) {
  const map = auditLoad();
  delete map[target];
  auditSave(map);
}
function auditUpdateCount() {
  const n = Object.keys(auditLoad()).length;
  const badge = document.getElementById("audit-count");
  if (badge) badge.textContent = String(n);
}

// Canonical target string: "<kind>:<id>:<field>"
function auditTarget(kind, id, field) { return `${kind}:${id}:${field}`; }

// On-disk applying path for a given kind/id/field.
// Returns null for pass kind: the build keys pass overrides by raw platform slug
// (pass:{library_id}__{rawslug}), but the panel only knows the canonical
// attraction_slug — so any data/overrides/passes/... path the panel could emit
// would NOT match load_overrides and would never apply. We therefore decline to
// present an applying path for pass records (see auditPathNote).
function auditDiskPath(kind, id, field) {
  if (kind === "pass") return null;
  const kindDir = { library: "libraries", attraction: "attractions", branch: "branches" }[kind] || kind + "s";
  return `data/overrides/${kindDir}/${id}/${field}.json`;
}

// Human-readable note shown in place of an applying path for pass records.
const PASS_INFO_NOTE = "信息性标注（不参与构建合并；pass 纠错需用 raw slug 手工处理）";

// Suggested download filename (double-underscore to avoid path separator issues)
function auditFileName(kind, id, field) {
  const kindDir = { library: "libraries", attraction: "attractions", branch: "branches", pass: "passes" }[kind] || kind + "s";
  return `${kindDir}__${id.replace(/[^a-z0-9_.-]/gi, "_")}__${field}.json`;
}

function auditGetAuditor() {
  return (document.getElementById("auditor-name")?.value || "admin").trim() || "admin";
}

// ── Cell action helpers ──────────────────────

// Whether corrected is allowed for this kind
function auditCanCorrect(kind) { return kind === "library" || kind === "attraction" || kind === "branch"; }

// Open the inline editor for a cell
// spec: { kind, id, field, currentValue }
let _editorSpec = null;
function auditOpenEditor(spec) {
  _editorSpec = spec;
  const ed = document.getElementById("override-editor");
  const backdrop = document.getElementById("override-editor-backdrop");
  document.getElementById("ed-title").textContent = auditTarget(spec.kind, spec.id, spec.field);

  // Prefill from existing record if any
  const existing = auditGet(auditTarget(spec.kind, spec.id, spec.field));
  const edStatus = document.getElementById("ed-status");
  const edValue = document.getElementById("ed-value");
  const edNote = document.getElementById("ed-note");
  const correctedRow = document.getElementById("ed-corrected-row");

  // Disable corrected option if not applicable
  const correctedOpt = edStatus.querySelector('option[value="corrected"]');
  if (correctedOpt) {
    correctedOpt.disabled = !auditCanCorrect(spec.kind);
    correctedOpt.textContent = auditCanCorrect(spec.kind)
      ? "✏️ 改值 (corrected)"
      : "✏️ 改值 (corrected) — 此类型不支持自动应用";
  }

  if (existing) {
    edStatus.value = existing.status;
    const currentRawVal = existing.corrected_value !== null && existing.corrected_value !== undefined
      ? JSON.stringify(existing.corrected_value, null, 2) : "";
    edValue.value = currentRawVal;
    edNote.value = existing.note || "";
  } else {
    edStatus.value = "reviewed";
    // Prefill with current value as JSON
    const cv = spec.currentValue !== undefined
      ? (typeof spec.currentValue === "string" ? JSON.stringify(spec.currentValue) : JSON.stringify(spec.currentValue, null, 2))
      : "";
    edValue.value = cv;
    edNote.value = "";
  }

  correctedRow.hidden = edStatus.value !== "corrected";
  document.getElementById("ed-json-hint").textContent = "";
  edValue.classList.remove("error");

  ed.hidden = false;
  backdrop.hidden = false;
}

function auditCloseEditor() {
  document.getElementById("override-editor").hidden = true;
  document.getElementById("override-editor-backdrop").hidden = true;
  _editorSpec = null;
}

// Light shape validation for known object fields. Returns an error string on
// failure, or null when the value is acceptable (or the field is unknown).
const VE_RESIDENCY_ENUM = ["none", "unknown", "ma_resident", "town_resident", "town_or_works"];
const RESV_REQUIRED_ENUM = ["none", "unknown", "timed_entry", "walk_in_ok"];
function auditValidateShape(field, value) {
  if (field === "visitor_eligibility") {
    if (value === null || typeof value !== "object" || Array.isArray(value)) {
      return "visitor_eligibility 必须是对象";
    }
    if (!("residency" in value)) return "缺少 residency 键";
    if (!VE_RESIDENCY_ENUM.includes(value.residency)) {
      return `residency 必须是 ${VE_RESIDENCY_ENUM.join(" / ")} 之一`;
    }
    return null;
  }
  if (field === "reservation") {
    if (value === null || typeof value !== "object" || Array.isArray(value)) {
      return "reservation 必须是对象";
    }
    if (!("required" in value)) return "缺少 required 键";
    if (!RESV_REQUIRED_ENUM.includes(value.required)) {
      return `required 必须是 ${RESV_REQUIRED_ENUM.join(" / ")} 之一`;
    }
    return null;
  }
  return null;
}

function auditSaveEditor() {
  if (!_editorSpec) return;
  const status = document.getElementById("ed-status").value;
  const noteVal = document.getElementById("ed-note").value.trim();
  const hint = document.getElementById("ed-json-hint");
  const textarea = document.getElementById("ed-value");

  let correctedValue = null;
  if (status === "corrected") {
    const raw = textarea.value.trim();
    if (!raw) {
      hint.textContent = "改值不能为空";
      textarea.classList.add("error");
      return;
    }
    try {
      correctedValue = JSON.parse(raw);
      hint.textContent = "";
      textarea.classList.remove("error");
    } catch (e) {
      hint.textContent = `JSON 解析错误: ${e.message}`;
      textarea.classList.add("error");
      return;
    }
    // Light shape validation for known object fields so a structurally-wrong-
    // but-valid-JSON value can't be saved and later break the frontend engine.
    const shapeErr = auditValidateShape(_editorSpec.field, correctedValue);
    if (shapeErr) {
      hint.textContent = "结构校验失败: " + shapeErr;
      textarea.classList.add("error");
      return;
    }
  }

  const target = auditTarget(_editorSpec.kind, _editorSpec.id, _editorSpec.field);
  const record = {
    target,
    kind: _editorSpec.kind,
    id: _editorSpec.id,
    field: _editorSpec.field,
    status,
    corrected_value: correctedValue,
    note: noteVal,
    audited_at: new Date().toISOString(),
    audited_by: auditGetAuditor(),
  };
  auditSet(record);
  auditCloseEditor();
  // Re-render current lens so badges appear
  renderLens();
}

// Open popover showing the stored record for a target
let _popoverTarget = null;
function auditOpenPopover(target, anchorEl) {
  _popoverTarget = target;
  const record = auditGet(target);
  if (!record) return;

  const pop = document.getElementById("override-popover");
  document.getElementById("pop-target").textContent = target;

  const body = document.getElementById("pop-body");
  body.innerHTML = "";

  function row(label, val, mono) {
    const rowEl = document.createElement("div");
    rowEl.className = "popover-row";
    const lbl = document.createElement("span");
    lbl.className = "popover-label";
    lbl.textContent = label;
    const v = document.createElement("span");
    v.className = "popover-val" + (mono ? " mono" : "");
    v.textContent = val;
    rowEl.appendChild(lbl);
    rowEl.appendChild(v);
    body.appendChild(rowEl);
  }

  const statusEmoji = { corrected: "✏️", reviewed: "✅", noted: "📝" }[record.status] || "";
  row("状态", `${statusEmoji} ${record.status}`);
  if (record.status === "corrected" && record.corrected_value !== null) {
    row("改值", JSON.stringify(record.corrected_value), true);
  }
  if (record.note) row("备注", record.note);
  row("审计人", record.audited_by);
  row("时间", record.audited_at ? record.audited_at.replace("T", " ").slice(0, 19) + " UTC" : "—");
  // Show on-disk applying path — or, for pass records, an explicit
  // "informational only / not auto-merged" note instead of a misleading path.
  const pathHint = document.createElement("div");
  pathHint.className = "popover-row";
  pathHint.style.cssText = "flex-direction:column;gap:2px;margin-top:4px;border-top:1px solid var(--rule);padding-top:6px;";
  const diskPath = auditDiskPath(record.kind, record.id, record.field);
  const ph = document.createElement("span");
  ph.className = "popover-label";
  const pv = document.createElement("span");
  pv.className = "popover-val mono";
  pv.style.fontSize = "10px";
  if (diskPath) {
    ph.textContent = "目标路径";
    pv.textContent = diskPath;
  } else {
    ph.textContent = "合并状态";
    pv.classList.remove("mono");
    pv.style.color = "var(--au)";
    pv.textContent = "⚠ 仅记录，不自动合并 · " + PASS_INFO_NOTE;
  }
  pathHint.appendChild(ph);
  pathHint.appendChild(pv);
  body.appendChild(pathHint);

  pop.hidden = false;

  // Position near the anchor
  if (anchorEl) {
    const rect = anchorEl.getBoundingClientRect();
    pop.style.left = Math.min(rect.left, window.innerWidth - 400) + "px";
    pop.style.top = (rect.bottom + 4) + "px";
  } else {
    pop.style.left = "50%";
    pop.style.top = "50%";
    pop.style.transform = "translate(-50%,-50%)";
  }
}

function auditClosePopover() {
  document.getElementById("override-popover").hidden = true;
  _popoverTarget = null;
}

// ── Cell wrapping helper ─────────────────────

// Wrap a <td> element to make it "audit-editable".
// spec: { kind, id, field, currentValue }
// Returns the modified td element.
function makeAuditableCell(td, spec) {
  td.classList.add("cell-editable");
  td.style.position = "relative";
  td.style.paddingBottom = "22px"; // room for badge

  // Hover action buttons
  const actions = document.createElement("div");
  actions.className = "cell-actions";

  // ✅ reviewed
  const btnReview = document.createElement("button");
  btnReview.className = "audit-action-btn";
  btnReview.title = "已核 (reviewed)";
  btnReview.textContent = "✅";
  btnReview.addEventListener("click", (e) => {
    e.stopPropagation();
    const target = auditTarget(spec.kind, spec.id, spec.field);
    const existing = auditGet(target);
    auditSet({
      target, kind: spec.kind, id: spec.id, field: spec.field,
      status: "reviewed",
      corrected_value: null,
      note: existing?.note || "",
      audited_at: new Date().toISOString(),
      audited_by: auditGetAuditor(),
    });
    renderLens();
  });
  actions.appendChild(btnReview);

  // ✏️ corrected (only for library/attraction/branch)
  if (auditCanCorrect(spec.kind)) {
    const btnCorrect = document.createElement("button");
    btnCorrect.className = "audit-action-btn";
    btnCorrect.title = "改值 (corrected)";
    btnCorrect.textContent = "✏️";
    btnCorrect.addEventListener("click", (e) => {
      e.stopPropagation();
      auditOpenEditor({ ...spec, status: "corrected" });
    });
    actions.appendChild(btnCorrect);
  }

  // 📝 noted
  const btnNote = document.createElement("button");
  btnNote.className = "audit-action-btn";
  btnNote.title = "备注 (noted)";
  btnNote.textContent = "📝";
  btnNote.addEventListener("click", (e) => {
    e.stopPropagation();
    auditOpenEditor({ ...spec, status: "noted" });
  });
  actions.appendChild(btnNote);

  td.appendChild(actions);

  // For pass-kind cells, surface an explicit "informational only" affordance so
  // the operator never assumes a pass annotation round-trips into the build.
  if (spec.kind === "pass") {
    const info = document.createElement("span");
    info.className = "pass-info-tag";
    info.textContent = "ⓘ 仅标注";
    info.title = PASS_INFO_NOTE;
    td.appendChild(info);
  }

  // Override badge if record exists
  refreshCellBadge(td, spec);

  return td;
}

function refreshCellBadge(td, spec) {
  // Remove existing badge
  const existing = td.querySelector(".override-badge");
  if (existing) existing.remove();

  const target = auditTarget(spec.kind, spec.id, spec.field);
  const record = auditGet(target);
  if (!record) return;

  const emoji = { corrected: "✏️", reviewed: "✅", noted: "📝" }[record.status] || "?";
  const cls = `override-badge override-badge-${record.status}`;
  const badge = document.createElement("span");
  badge.className = cls;
  badge.textContent = emoji + " " + record.status;
  badge.title = `点击查看详情 · ${target}`;
  badge.addEventListener("click", (e) => {
    e.stopPropagation();
    auditOpenPopover(target, badge);
  });
  td.appendChild(badge);
}

// ── Lens wrappers that add audit cells ───────

// Lens B: Library rows — auditable fields: card_eligibility, pass_pickup_default
function buildLensBWithAudit() {
  const colDefs = [
    { label: "图书馆", sticky: true },
    { label: "联盟(Network)" },
    { label: "办卡资格(card_eligibility) ✏️" },
    { label: "取 pass 资格(pass_pickup_default) ✏️" },
    { label: "办卡页面" },
  ];

  const groupedRows = {};
  for (const lib of STATE.libs) {
    if (!STATE.selectedLibs.has(lib.id)) continue;
    const net = lib.network || "Unknown";
    const tr = el("tr");
    const libShort = lib.name.replace(/\sPublic Library$|\sLibrary$/, "");
    tr.appendChild(el("td", { class: "col-sticky" }, libShort));
    tr.appendChild(el("td", {}, net));

    // card_eligibility — auditable
    const ce = lib.card_eligibility || "unknown";
    const ceTd = el("td", {}, eligTag(ce), el("span", { style: "margin-left:6px;font-size:11px;color:var(--ink-3)" }, ce));
    makeAuditableCell(ceTd, { kind: "library", id: lib.id, field: "card_eligibility", currentValue: lib.card_eligibility });
    tr.appendChild(ceTd);

    // pass_pickup_default — auditable
    const pp = lib.pass_pickup_default || "unknown";
    const ppTd = el("td", {}, el("span", { style: "font-size:12px" }, pp));
    makeAuditableCell(ppTd, { kind: "library", id: lib.id, field: "pass_pickup_default", currentValue: lib.pass_pickup_default });
    tr.appendChild(ppTd);

    // card_page
    const link = lib.card_page
      ? el("a", { href: lib.card_page, target: "_blank", class: "lib-name-link" }, "办卡页 ↗")
      : el("span", { style: "color:var(--ink-3)" }, "—");
    tr.appendChild(el("td", {}, link));
    (groupedRows[net] ||= []).push(tr);
  }

  return buildGroupedTable(colDefs, groupedRows);
}

// Lens D: Attraction rows — auditable fields: visitor_eligibility, reservation, prices
function buildLensDWithAudit() {
  const colDefs = [
    { label: "景点", sticky: true },
    { label: "访客居住资格(visitor_eligibility) ✏️" },
    { label: "预约要求(reservation) ✏️" },
    { label: "持卡人通道" },
    { label: "提供此景点pass的图书馆" },
  ];

  const rows = [];
  for (const attr of STATE.attractions) {
    if (STATE.categoryFilter && !(attr.categories || []).includes(STATE.categoryFilter)) continue;
    const coveringPasses = (STATE.passesByAttr[attr.slug] || []).filter(p => STATE.selectedLibs.has(p.library_id));
    if (STATE.showOnlyCovered && !coveringPasses.length) continue;

    const tr = el("tr");
    // Attraction col
    tr.appendChild(el("td", { class: "col-sticky" },
      el("span", { class: "attr-name-serif" }, attr.name),
      attr.address?.city ? el("div", { style: "font-size:11px;color:var(--ink-3);margin-top:2px" }, attr.address.city + ", MA") : null,
    ));

    // visitor_eligibility — auditable
    const ve = attr.visitor_eligibility;
    const veStr = ve ? ve.residency : "unknown";
    const veNote = ve?.note;
    const veTd = el("td", {},
      el("span", { style: "font-size:12px" }, veStr),
      veNote ? el("div", { style: "font-size:11px;color:var(--ink-3);margin-top:2px" }, veNote) : null,
    );
    makeAuditableCell(veTd, { kind: "attraction", id: attr.slug, field: "visitor_eligibility", currentValue: attr.visitor_eligibility });
    tr.appendChild(veTd);

    // reservation — auditable
    const resv = attr.reservation;
    let resvBadge;
    if (!resv || resv.required === "none") resvBadge = el("span", { class: "resv-none" }, "无需预约");
    else if (resv.required === "timed_entry") resvBadge = el("span", { class: "resv-required" }, "需定时票");
    else resvBadge = el("span", { class: "resv-walkin" }, "Walk-in OK");
    const resvTd = el("td", {}, resvBadge);
    if (resv?.booking_url) {
      resvTd.appendChild(el("div", { style: "margin-top:4px" },
        el("a", { href: resv.booking_url, target: "_blank", class: "lib-name-link" }, "预约链接 ↗")
      ));
    }
    if (resv?.lead_time_hours) {
      resvTd.appendChild(el("div", { style: "font-size:11px;color:var(--ink-3);margin-top:2px" }, `提前 ${resv.lead_time_hours}h`));
    }
    makeAuditableCell(resvTd, { kind: "attraction", id: attr.slug, field: "reservation", currentValue: attr.reservation });
    tr.appendChild(resvTd);

    // pass_holder_url
    const phu = resv?.pass_holder_url;
    const phuCell = phu
      ? el("td", {}, el("a", { href: phu, target: "_blank", class: "lib-name-link" }, "持卡通道 ↗"))
      : el("td", {}, el("span", { style: "color:var(--ink-3)" }, "—"));
    tr.appendChild(phuCell);

    // Libraries providing this attraction
    const libCell = el("td");
    if (!coveringPasses.length) {
      libCell.appendChild(el("span", { style: "color:var(--ink-3)" }, "—"));
    } else {
      for (const pass of coveringPasses) {
        const lib = STATE.libsById[pass.library_id];
        if (!lib) continue;
        const libShort = lib.name.replace(/\sPublic Library$|\sLibrary$/, "");
        const branchInfo = pass.available_at_branches === "all"
          ? "所有分馆"
          : (Array.isArray(pass.available_at_branches) ? pass.available_at_branches.join(", ") : String(pass.available_at_branches));
        libCell.appendChild(el("div", { class: "ap-row" },
          el("span", { class: "ap-label" }, libShort + " "),
          el("span", { style: "font-size:11px;color:var(--ink-3)" }, `[${branchInfo}]`),
        ));
      }
    }
    tr.appendChild(libCell);
    rows.push(tr);
  }

  return buildTable(colDefs, rows);
}

// Lens A: Pass rows — reviewed/noted only (no corrected for passes)
function buildLensAWithAudit() {
  const user = getUser();
  const date = STATE.visitDate;
  const iso = date ? date.toISOString().slice(0, 10) : null;

  const colDefs = [
    { label: "图书馆", sticky: true },
    { label: "景点" },
    { label: "我合规吗" },
    { label: "一句话优惠摘要 ✅/📝" },
    { label: "当日库存" },
    { label: "来源" },
  ];

  const groupedRows = {};
  for (const lib of STATE.libs) {
    if (!STATE.selectedLibs.has(lib.id)) continue;
    const net = lib.network || "Unknown";
    const libPasses = STATE.passesByLib[lib.id] || [];
    for (const pass of libPasses) {
      const attr = STATE.attrBySlug[pass.attraction_slug];
      if (STATE.categoryFilter && !(attr?.categories || []).includes(STATE.categoryFilter)) continue;
      // Audit tool: the toggle filters on "has coupon/coverage data present",
      // NOT on eligibility. Eligibility is shown as a verdict badge but never
      // used to HIDE rows — an auditor needs to see ineligible/blocked passes.
      if (STATE.showOnlyCovered && !pass.coupon) continue;
      const verdict = resolvePass(pass, lib, attr, user, date);
      const tr = el("tr");
      const libShort = lib.name.replace(/\sPublic Library$|\sLibrary$/, "");
      tr.appendChild(el("td", { class: "col-sticky" }, libShort));
      const attrName = attr ? el("span", { class: "attr-name-serif" }, attr.name) : el("span", {}, pass.attraction_slug);
      tr.appendChild(el("td", {}, attrName));
      const vb = verdictBadge(verdict);
      const vCont = el("td", {}, vb);
      if (!verdict.eligible && verdict.reasons?.length) {
        vCont.appendChild(el("div", { class: "cell-reason" }, verdict.reasons.join(" · ")));
      }
      if (verdict.warnings?.length) {
        vCont.appendChild(el("div", { class: "cell-warn-reason" }, "⚠ " + verdict.warnings.join(" · ")));
      }
      tr.appendChild(vCont);

      // Summary col — auditable (reviewed/noted only for passes)
      const summary = couponSummary(pass.coupon);
      const summaryTd = el("td", {}, el("span", { class: "cell-summary" }, summary));
      // Pass id uses best-effort <library_id>__<attraction_slug> — note key ambiguity
      const passId = `${pass.library_id}__${pass.attraction_slug}`;
      makeAuditableCell(summaryTd, { kind: "pass", id: passId, field: "coupon_summary", currentValue: summary });
      tr.appendChild(summaryTd);

      tr.appendChild(el("td", {}, availBadge(pass, iso)));
      const srcBtn = pass.source_url
        ? el("button", { class: "book-link", onclick: () => window.open(pass.source_url, "_blank", "noopener,noreferrer") }, "Book →")
        : el("span", { style: "color:var(--ink-3)" }, "—");
      tr.appendChild(el("td", {}, srcBtn));

      (groupedRows[net] ||= []).push(tr);
    }
  }

  return buildGroupedTable(colDefs, groupedRows);
}

// Lens C: Pass rows — reviewed/noted only
function buildLensCWithAudit() {
  const colDefs = [
    { label: "图书馆", sticky: true },
    { label: "景点" },
    { label: "人群条款(audience_policies) ✅/📝" },
    { label: "容量(capacity)" },
    { label: "pass_form" },
  ];

  const groupedRows = {};
  for (const lib of STATE.libs) {
    if (!STATE.selectedLibs.has(lib.id)) continue;
    const net = lib.network || "Unknown";
    const libPasses = STATE.passesByLib[lib.id] || [];

    for (const pass of libPasses) {
      const attr = STATE.attrBySlug[pass.attraction_slug];
      if (STATE.categoryFilter && !(attr?.categories || []).includes(STATE.categoryFilter)) continue;
      if (STATE.showOnlyCovered && !pass.coupon) continue;

      const tr = el("tr");
      const libShort = lib.name.replace(/\sPublic Library$|\sLibrary$/, "");
      tr.appendChild(el("td", { class: "col-sticky" }, libShort));
      const attrName = attr ? el("span", { class: "attr-name-serif" }, attr.name) : el("span", {}, pass.attraction_slug);
      tr.appendChild(el("td", {}, attrName));

      // Audience policies — auditable (noted/reviewed only for pass)
      const apCell = el("td");
      const policies = pass.coupon?.audience_policies || [];
      if (!policies.length) {
        apCell.appendChild(el("span", { style: "color:var(--ink-3)" }, "—"));
      } else {
        for (const ap of policies) {
          const parts = [];
          if (ap.audience) parts.push(ap.audience);
          const formVal = ap.form + (ap.value != null ? `=${ap.value}` : "");
          parts.push(formVal);
          if (ap.age_range) {
            const { min, max } = ap.age_range;
            if (min != null && max != null) parts.push(`age ${min}-${max}`);
            else if (max != null) parts.push(`age<${max + 1}`);
            else if (min != null) parts.push(`age ${min}+`);
          }
          if (ap.count != null) parts.push(`×${ap.count}`);
          apCell.appendChild(el("div", { class: "ap-row" },
            el("span", { class: "ap-label" }, parts.slice(0, -1).join(" · ") + (parts.length > 1 ? " → " : "")),
            el("span", { class: "ap-val" }, parts[parts.length - 1]),
          ));
        }
      }
      const passId = `${pass.library_id}__${pass.attraction_slug}`;
      makeAuditableCell(apCell, { kind: "pass", id: passId, field: "audience_policies", currentValue: pass.coupon?.audience_policies });
      tr.appendChild(apCell);

      const cap = pass.coupon?.capacity;
      const capStr = cap && cap.n != null ? `${cap.kind} × ${cap.n}` : "—";
      tr.appendChild(el("td", {}, el("span", { class: "cap-label" }, capStr)));
      tr.appendChild(el("td", {}, passFormPill(pass.pass_form)));
      (groupedRows[net] ||= []).push(tr);
    }
  }

  return buildGroupedTable(colDefs, groupedRows);
}

// ── Export ────────────────────────────────────

function downloadBlob(content, filename) {
  const blob = new Blob([content], { type: "application/json;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click();
  setTimeout(() => { document.body.removeChild(a); URL.revokeObjectURL(url); }, 200);
}

function auditExportPerFile() {
  const map = auditLoad();
  const entries = Object.values(map);
  if (!entries.length) { alert("尚无审计记录。"); return; }
  for (const record of entries) {
    const filename = auditFileName(record.kind, record.id, record.field);
    let out = record;
    if (record.kind === "pass") {
      // Pass overrides do NOT round-trip into the build (raw-slug keying). Stamp
      // the exported file so an operator can't mistake it for an applying override.
      out = { ...record, _informational_only: true, _note: PASS_INFO_NOTE };
    }
    downloadBlob(JSON.stringify(out, null, 2), filename);
  }
  // Show path hints (and pass disclosure) in the audit log
  auditRenderLog(true);
}

function auditExportBundle() {
  const map = auditLoad();
  if (!Object.keys(map).length) { alert("尚无审计记录。"); return; }
  const bundle = { _generated_at: new Date().toISOString(), overrides: map };
  downloadBlob(JSON.stringify(bundle, null, 2), "overrides_bundle.json");
}

// ── Audit Log ─────────────────────────────────

function auditRenderLog(showPaths) {
  const listEl = document.getElementById("audit-log-list");
  if (!listEl) return;
  listEl.innerHTML = "";

  const map = auditLoad();
  let entries = Object.values(map);

  // Apply filters
  const fieldFilter = (document.getElementById("al-filter-field")?.value || "").toLowerCase();
  const auditorFilter = (document.getElementById("al-filter-auditor")?.value || "").toLowerCase();
  const statusFilter = document.getElementById("al-filter-status")?.value || "";
  const dateFrom = document.getElementById("al-date-from")?.value || "";
  const dateTo = document.getElementById("al-date-to")?.value || "";

  if (fieldFilter) entries = entries.filter(r => r.field?.toLowerCase().includes(fieldFilter) || r.target?.toLowerCase().includes(fieldFilter));
  if (auditorFilter) entries = entries.filter(r => r.audited_by?.toLowerCase().includes(auditorFilter));
  if (statusFilter) entries = entries.filter(r => r.status === statusFilter);
  if (dateFrom) entries = entries.filter(r => r.audited_at >= dateFrom);
  if (dateTo) entries = entries.filter(r => r.audited_at <= dateTo + "T23:59:59Z");

  // Sort newest first
  entries.sort((a, b) => (b.audited_at || "") > (a.audited_at || "") ? 1 : -1);

  if (!entries.length) {
    listEl.appendChild(el("div", { class: "audit-log-empty" }, "暂无匹配记录"));
    return;
  }

  for (const record of entries) {
    const entry = el("div", { class: `audit-log-entry entry-${record.status}` });

    const meta = el("div", { class: "ale-meta" });
    meta.appendChild(el("div", { class: "ale-target" }, record.target));

    const detail = el("div", { class: "ale-detail" },
      `${record.kind} · ${record.id} · ${record.field}`,
    );
    meta.appendChild(detail);

    if (record.status === "corrected" && record.corrected_value !== null) {
      meta.appendChild(el("div", { class: "ale-value" }, "→ " + JSON.stringify(record.corrected_value)));
    }
    if (record.note) {
      meta.appendChild(el("div", { class: "ale-note" }, "📝 " + record.note));
    }
    // Pass records are informational only — always disclose, regardless of showPaths.
    if (record.kind === "pass") {
      meta.appendChild(el("div", { class: "ale-path-hint", style: "color:var(--au)" },
        "⚠ 仅记录，不自动合并 · " + PASS_INFO_NOTE));
    } else if (showPaths) {
      const pathStr = auditDiskPath(record.kind, record.id, record.field);
      meta.appendChild(el("div", { class: "ale-path-hint" }, "→ " + pathStr));
    }

    const right = el("div", { class: "ale-right" });
    const emoji = { corrected: "✏️", reviewed: "✅", noted: "📝" }[record.status] || "";
    right.appendChild(el("span", { class: "ale-auditor" }, emoji + " " + (record.audited_by || "")));
    right.appendChild(el("span", { class: "ale-time" }, record.audited_at ? record.audited_at.slice(0, 19).replace("T", " ") : "—"));
    const delBtn = el("button", { class: "btn-tiny", style: "font-size:10px;color:var(--rd);border-color:var(--rd)" }, "撤销");
    delBtn.addEventListener("click", () => {
      if (confirm(`撤销记录: ${record.target}?`)) {
        auditDelete(record.target);
        renderLens();
      }
    });
    right.appendChild(delBtn);

    entry.appendChild(meta);
    entry.appendChild(right);
    listEl.appendChild(entry);
  }
}

// ── Init audit system ─────────────────────────

function initAuditSystem() {
  auditUpdateCount();

  // Editor status change
  document.getElementById("ed-status").addEventListener("change", (e) => {
    document.getElementById("ed-corrected-row").hidden = e.target.value !== "corrected";
  });

  // Editor save/cancel/close
  document.getElementById("ed-save").addEventListener("click", auditSaveEditor);
  document.getElementById("ed-cancel").addEventListener("click", auditCloseEditor);
  document.getElementById("ed-close").addEventListener("click", auditCloseEditor);
  document.getElementById("override-editor-backdrop").addEventListener("click", auditCloseEditor);

  // Popover close / revoke
  document.getElementById("pop-close").addEventListener("click", auditClosePopover);
  document.getElementById("pop-revoke").addEventListener("click", () => {
    if (_popoverTarget && confirm(`撤销记录: ${_popoverTarget}?`)) {
      auditDelete(_popoverTarget);
      auditClosePopover();
      renderLens();
    }
  });
  // Close popover on outside click
  document.addEventListener("click", (e) => {
    const pop = document.getElementById("override-popover");
    if (!pop.hidden && !pop.contains(e.target)) auditClosePopover();
  });

  // Export buttons
  document.getElementById("btn-export-overrides").addEventListener("click", auditExportPerFile);
  document.getElementById("btn-export-bundle").addEventListener("click", auditExportBundle);

  // Audit log toggle
  const logToggle = document.getElementById("audit-log-toggle");
  const logBody = document.getElementById("audit-log-body");
  const logChevron = document.getElementById("audit-log-chevron");
  function toggleLog() {
    const isOpen = !logBody.hidden;
    logBody.hidden = isOpen;
    logChevron.classList.toggle("open", !isOpen);
    logToggle.setAttribute("aria-expanded", String(!isOpen));
    if (!isOpen) auditRenderLog();
  }
  logToggle.addEventListener("click", toggleLog);
  logToggle.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggleLog(); } });

  // Audit log filters
  ["al-filter-field", "al-filter-auditor", "al-filter-status", "al-date-from", "al-date-to"].forEach(id => {
    document.getElementById(id)?.addEventListener("input", () => auditRenderLog());
    document.getElementById(id)?.addEventListener("change", () => auditRenderLog());
  });
  document.getElementById("al-clear-filters")?.addEventListener("click", () => {
    ["al-filter-field", "al-filter-auditor"].forEach(id => { const el = document.getElementById(id); if (el) el.value = ""; });
    ["al-filter-status"].forEach(id => { const el = document.getElementById(id); if (el) el.value = ""; });
    ["al-date-from", "al-date-to"].forEach(id => { const el = document.getElementById(id); if (el) el.value = ""; });
    auditRenderLog();
  });
}

init().catch((e) => {
  console.error(e);
  $("#stat-summary").textContent = "加载错误: " + e.message;
  const mc = $("#matrix-container"); if (mc) mc.innerHTML = `<div class="loading-msg" style="color:var(--rd)">加载失败: ${e.message}</div>`;
});
