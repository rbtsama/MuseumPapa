// MuseumPapa Admin Panel — rebuilt on new data shapes + funnel engine
// Edit source under admin/ only. See web/sync-admin.mjs for copy rules.

import { cardOk, residencyOk, cellTier, availStatus, rowSortKey, bestPolicy, couponSummary, shortSummary } from "./panel.logic.mjs";
import { buildRecord, buildFeedbackRecord, ASPECTS } from "./panel.audit.mjs";

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
  onlyEligible: true,   // card + zip confirmed (the eligibility dimension)
  onlyInStock: true,    // confirmed available on the date (the inventory dimension)
  showStock: false,     // show the per-cell availability styling (left-border accent); off = data-verification mode
  display: { policies:false, verdict:false, pickup:false, avail:false, distance:false, restrict:false, warn:false },
  // group collapse state: net -> bool collapsed
  groupCollapsed: {},
  audits: {},
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
//  SHARED AUDIT STORE TRANSPORT
// ─────────────────────────────────────────────
// Shared audit store (Plan 1 /api/overrides), with localStorage fallback when no endpoint.
const AUDIT_LS_V3 = "mp_audit_overrides";
async function auditLoadAll() {
  try { const r = await fetch("/api/overrides"); if (r.ok) return await r.json(); } catch (e) {}
  try { return JSON.parse(localStorage.getItem(AUDIT_LS_V3) || "{}"); } catch (e) { return {}; }
}
async function auditPut(record) {
  STATE.audits[record.target] = record;
  try {
    const r = await fetch("/api/overrides", { method:"POST",
      headers:{"Content-Type":"application/json"}, body: JSON.stringify(record) });
    if (r.ok) { STATE.audits = await r.json(); return; }
  } catch (e) {}
  try { localStorage.setItem(AUDIT_LS_V3, JSON.stringify(STATE.audits)); } catch (e) {}
}
async function auditRevoke(target) {
  delete STATE.audits[target];
  try {
    const r = await fetch("/api/overrides", { method:"POST",
      headers:{"Content-Type":"application/json"}, body: JSON.stringify({revoke:target}) });
    if (r.ok) { STATE.audits = await r.json(); return; }
  } catch (e) {}
  try { localStorage.setItem(AUDIT_LS_V3, JSON.stringify(STATE.audits)); } catch (e) {}
}
// any audit record on this pass? returns the record's status or null
function passAuditStatus(cell) {
  const prefix = `pass:${cell.lib.id}__${cell.pass.attraction_rawslug}:`;
  for (const t of Object.keys(STATE.audits || {})) if (t.startsWith(prefix)) return STATE.audits[t].status;
  return null;
}

// ─────────────────────────────────────────────
//  DATA LOAD
// ─────────────────────────────────────────────
// Persist the operator's filter/display selections so a refresh keeps them.
const PANEL_STATE_KEY = "mp_panel_state";
function persistPanelState() {
  try {
    localStorage.setItem(PANEL_STATE_KEY, JSON.stringify({
      libs: [...STATE.selectedLibs], attrs: [...STATE.selectedAttrs],
      zip: STATE.homeZip, date: STATE.visitDate ? STATE.visitDate.toISOString().slice(0, 10) : null,
      onlyEligible: STATE.onlyEligible, onlyInStock: STATE.onlyInStock, showStock: STATE.showStock, display: STATE.display,
    }));
  } catch (e) { /* storage unavailable — ignore */ }
}
function loadPanelState() {
  try { return JSON.parse(localStorage.getItem(PANEL_STATE_KEY) || "null"); } catch (e) { return null; }
}

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
  town_resident: "Town",
  town_or_works: "Town/Work",
  network: "Network",
  none: "Open",
  unknown: "?",
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
  digital_email: { label: "Email", cls: "pf-email" },     // green — instant
  physical_coupon: { label: "Pickup", cls: "pf-pickup" }, // orange — go to library
  physical_circ: { label: "Pik & Rtn", cls: "pf-rtn" },   // red — pick up AND return
};
// transparent colored tag used in the matrix, detail popup, and booking popup
function pfTag(f) {
  const m = PASS_FORM_META[f] || { label: f || "—", cls: "pf-unknown" };
  return el("span", { class: `pf-tag ${m.cls}` }, m.label);
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
        el("span", { class: "card-member-name", title: l.name }, l.town),
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
//  MAIN RENDER DISPATCHER
// ─────────────────────────────────────────────

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
//  MATRIX MODEL + RENDERER
// ─────────────────────────────────────────────

// Build { columns:[{net,libs:[lib]}], rows:[{attr, cells:{lib_id:{pass,tier,avail,cardOk,zipOk,verdict}}}] }
function buildMatrixModel() {
  const user = getUser();
  const held = user.heldLibraryIds;
  const iso = STATE.visitDate ? STATE.visitDate.toISOString().slice(0, 10) : null;

  // rows: only selected attractions that have at least one pass
  const rows = [];
  // Every library that offers a selected attraction — its column is kept even when
  // filters empty all of its cells (don't hide columns; see operator request).
  const columnLibIds = new Set();
  for (const attr of STATE.attractions) {
    if (!STATE.selectedAttrs.has(attr.slug)) continue;
    const passes = STATE.passesByAttr[attr.slug] || [];
    if (!passes.length) continue;
    const cells = {};
    const cellList = [];
    for (const pass of passes) {
      const lib = STATE.libsById[pass.library_id];
      if (!lib) continue;
      columnLibIds.add(lib.id);
      const ck = cardOk(lib, held, STATE.libsById);
      const rz = residencyOk(pass, lib, attr, STATE.homeZip, STATE.MA_ZIPS);
      const tier = cellTier(ck, rz.ok);
      const avail = availStatus(pass, iso);
      // eligibility dimension (卡+Zip): strict — unknown residency does NOT count
      if (STATE.onlyEligible && !(tier === "a" && !rz.warn)) continue;
      // inventory dimension: only confirmed in stock (unknown/booked/closed excluded)
      if (STATE.onlyInStock && avail !== "available") continue;
      const verdict = resolvePass(pass, lib, attr, user, STATE.visitDate);
      const cell = { pass, lib, tier, avail, cardOk: ck, zipOk: rz.ok, warn: rz.warn, verdict };
      cells[lib.id] = cell;
      cellList.push({ tier, avail });
    }
    if ((STATE.onlyEligible || STATE.onlyInStock) && !cellList.length) continue; // row emptied by filters
    rows.push({ attr, cells, sortKey: rowSortKey(cellList) });
  }
  rows.sort((a, b) =>
    (a.sortKey[0] - b.sortKey[0]) || (a.sortKey[1] - b.sortKey[1]) || a.attr.name.localeCompare(b.attr.name));

  // columns: networks (held-card networks first). Keep every library that offers a
  // selected attraction, even if filters emptied all its cells — don't hide columns.
  const heldNets = new Set(held.map(id => STATE.libsById[id]?.network).filter(Boolean));
  const netOrder = STATE.networks.slice().sort((a, b) =>
    (heldNets.has(b) - heldNets.has(a)) || 0);
  const columns = [];
  for (const net of netOrder) {
    const libs = STATE.libsByNetwork[net].filter(l => columnLibIds.has(l.id));
    if (libs.length) columns.push({ net, libs });
  }
  return { columns, rows };
}

// funnel layer -> level marker (① card, ② pickup residency, ③ attraction residency, ④ date, ⑤ availability)
const LAYER_NUM = { L1: "①", L3: "②", L4: "③", L8: "④", L10: "⑤" };

function renderMatrix() {
  const container = $("#matrix-container");
  if (!container) return;
  persistPanelState();
  const { columns, rows } = buildMatrixModel();
  const flatLibs = columns.flatMap(c => c.libs);
  if (!flatLibs.length || !rows.length) {
    container.innerHTML = "";
    container.appendChild(el("div", { class: "loading-msg" }, "No matching data (adjust cards / attraction filter)"));
    return;
  }

  const netEndIds = new Set(columns.map(c => c.libs[c.libs.length - 1].id)); // last lib of each network
  const table = el("table", { class: "matrix-table" });
  // header row 1: network groups
  const thead = el("thead");
  const netTr = el("tr", { class: "mx-net-row" });
  netTr.appendChild(el("th", { class: "mx-corner", rowspan: "2" }, "Attraction ＼ Town"));
  for (const col of columns) {
    netTr.appendChild(el("th", { class: "mx-net mx-netend", colspan: String(col.libs.length) }, `${col.net} · ${col.libs.length}`));
  }
  thead.appendChild(netTr);
  // header row 2: library names
  const libTr = el("tr", { class: "mx-lib-row" });
  for (const lib of flatLibs) {
    const th = el("th", { class: "mx-lib", title: lib.name }, lib.town);
    if (netEndIds.has(lib.id)) th.classList.add("mx-netend");
    libTr.appendChild(th);
  }
  thead.appendChild(libTr);
  table.appendChild(thead);

  const tbody = el("tbody");
  for (const row of rows) {
    const tr = el("tr");
    tr.appendChild(el("th", { class: "mx-rowhead mx-rowhead-click", title: "click: your cards that can book this", onclick: () => openBookingPopup(row.attr) }, row.attr.name));
    for (const lib of flatLibs) {
      const cell = row.cells[lib.id];
      const td = cell ? renderCell(cell, row.attr) : el("td", { class: "mx-cell mx-empty" });
      if (netEndIds.has(lib.id)) td.classList.add("mx-netend");
      tr.appendChild(td);
    }
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  container.innerHTML = "";
  container.appendChild(table);
}

function renderCell(cell, attr) {
  const d = STATE.display;
  // availability accent (left border) only shown in "展示库存" mode
  const availCls = STATE.showStock
    ? (cell.avail === "available" ? "av-ok"
      : (cell.avail === "booked" || cell.avail === "closed") ? "av-no"
      : cell.avail === "unknown" ? "av-unk" : "")
    : "";
  // Single background state: red ONLY when the customer HOLDS the card but fails a
  // resident-only restriction. Eligible cells and no-card cells get no background.
  const bgCls = (cell.cardOk && !cell.zipOk) ? "mx-resident-block" : "";
  const td = el("td", { class: `mx-cell ${bgCls} ${availCls}` });

  // Offer: simplified (default) = adult/headline short glyph; "人群条款全展开" on
  // = every audience policy spelled out.
  if (d.policies && cell.pass.coupon?.audience_policies?.length) {
    for (const p of cell.pass.coupon.audience_policies)
      td.appendChild(el("div", { class: "mx-sub mx-pol" }, `${p.audience}: ${couponSummary({ audience_policies: [p] })}`));
  } else {
    td.appendChild(el("div", { class: "mx-glyph" }, shortSummary(cell.pass.coupon)));
  }

  if (d.warn && cell.warn) td.appendChild(el("span", { class: "mx-warn", title: "eligibility not confirmed (residency unknown in our data)" }, "⚠"));
  if (d.avail && cell.avail !== "none") td.appendChild(el("div", { class: "mx-sub" }, cell.avail));
  if (d.verdict && !cell.verdict.eligible) td.appendChild(el("div", { class: "mx-sub mx-block", title: `blocked at ${cell.verdict.blockedLayer}` }, `${LAYER_NUM[cell.verdict.blockedLayer] || ""} ${cell.verdict.reasons[0] || cell.verdict.blockedLayer}`.trim()));
  if (d.pickup) td.appendChild(el("div", { class: "mx-sub" }, pfTag(cell.pass.pass_form)));
  if (d.distance && cell.lib.geo && STATE.homeGeo) {
    const mi = haversineMi(STATE.homeGeo, cell.lib.geo);
    if (mi != null) td.appendChild(el("div", { class: "mx-sub" }, `${mi.toFixed(1)} mi`));
  }
  if (d.restrict && cell.pass.restrictions) {
    const r = cell.pass.restrictions, bits = [];
    if (r.weekdays_only) bits.push("weekdays only");
    if (r.seasonal) bits.push("seasonal");
    if (r.advance_booking_required) bits.push(`book ${r.advance_booking_hours || "?"}h ahead`);
    if (r.blackout?.length) bits.push(`${r.blackout.length} blackout date(s)`);
    if (r.blackout_recurring?.length) bits.push(`closed ${r.blackout_recurring.join("/")}`);
    if (r.booking_frequency_limit) bits.push(String(r.booking_frequency_limit));
    if (r.late_return_penalty) bits.push("late fee");
    if (bits.length) td.appendChild(el("div", { class: "mx-sub mx-restrict", title: r.late_return_penalty || "" }, bits.join(" · ")));
  }
  // whole cell opens the detail popup (offer / eligibility / source + actions)
  td.classList.add("mx-click");
  td.addEventListener("click", () => openDetailPopup(cell, attr));
  td.dataset.libId = cell.lib.id;
  td.dataset.attrSlug = attr.slug;
  const aStatus = passAuditStatus(cell);
  if (aStatus) {
    const sym = aStatus === "corrected" ? "✎" : aStatus === "verified_ok" ? "✓" : aStatus === "feedback" ? "💬" : "📝";
    td.appendChild(el("span", { class: `mx-audited mx-audited-${aStatus}`, title: `audited: ${aStatus}` }, sym));
  }
  return td;
}

// ── popups: booking options (per attraction) + source text (per cell) ──
function openModal(title, bodyNode) {
  $("#mx-modal-title").textContent = title;
  const body = $("#mx-modal-body"); body.innerHTML = ""; body.appendChild(bodyNode);
  $("#mx-modal").hidden = false;
}
function closeModal() { $("#mx-modal").hidden = true; }

// pickup-method order: Email (instant) first, then Pick-up, then Pick-up-and-Return.
const PICKUP_ORDER = { digital_email: 0, physical_coupon: 1, physical_circ: 2 };

// All HELD cards that offer this attraction; eligible first, then by pickup order.
// Email pass needs no distance; Pick-up / Pick-up-and-Return show distance to the library.
function openBookingPopup(attr) {
  const user = getUser();
  const held = new Set(user.heldLibraryIds);
  const rows = (STATE.passesByAttr[attr.slug] || [])
    .filter(p => held.has(p.library_id))
    .map(p => { const lib = STATE.libsById[p.library_id];
      return { p, lib, v: resolvePass(p, lib, attr, user, STATE.visitDate) }; })
    .sort((a, b) => (b.v.eligible - a.v.eligible)
      || ((PICKUP_ORDER[a.p.pass_form] ?? 9) - (PICKUP_ORDER[b.p.pass_form] ?? 9)));
  const box = el("div", { class: "bk-list" });
  if (!held.size) box.appendChild(el("p", { class: "hint" }, "Tick the cards you hold in the sidebar first."));
  else if (!rows.length) box.appendChild(el("p", { class: "hint" }, "None of your cards offer this attraction."));
  else for (const { p, lib, v } of rows) {
    const physical = p.pass_form !== "digital_email";
    const mi = (physical && lib.geo && STATE.homeGeo) ? haversineMi(STATE.homeGeo, lib.geo) : null;
    box.appendChild(el("div", { class: "bk-row" },
      el("div", { class: "bk-lib", title: lib.name }, lib.town),
      el("div", { class: "bk-offer" }, couponSummary(p.coupon)),
      pfTag(p.pass_form),
      el("span", { class: "bk-dist" }, mi != null ? `${mi.toFixed(1)} mi` : ""),
      v.eligible ? el("span", { class: "bk-ok" }, "✓") : el("span", { class: "bk-no" }, "✗ " + (v.reasons[0] || v.blockedLayer)),
      p.source_url ? el("a", { class: "bk-link", href: p.source_url, target: "_blank", rel: "noopener" }, "Book ↗")
                   : el("span", { class: "hint" }, "no link"),
    ));
  }
  openModal(`Book: ${attr.name}`, box);
}

// Raw provenance text for one pass (shown in the detail popup + used by Copy).
function buildSourceText(cell, attr) {
  const p = cell.pass, c = p.coupon, parts = [];
  parts.push(`${attr.name} × ${cell.lib.town}`);
  if (c?.summary) parts.push(`Offer: ${c.summary}`);
  if (c?.source_phrase_block) parts.push(`\n[coupon source]\n${c.source_phrase_block}`);
  for (const ap of (c?.audience_policies || [])) if (ap.source_phrase) parts.push(`\n[${ap.audience}]\n${ap.source_phrase}`);
  const rr = p.residency_restriction;
  if (rr && (rr.source || rr.evidence)) parts.push(`\n[residency ${rr.restricted}/${rr.scope || "-"} via ${rr.source || "?"}]\n${rr.evidence || ""}`);
  if (p.source_url) parts.push(`\n[booking page] ${p.source_url}`);
  return parts.join("\n").trim();
}

// Full cell detail popup: readable key facts (highlighted) + source text + actions.
function openDetailPopup(cell, attr) {
  const p = cell.pass, c = p.coupon, v = cell.verdict;
  const box = el("div", { class: "dt" });
  const kv = (k, val, cls) => el("div", { class: "dt-row" },
    el("span", { class: "dt-k" }, k),
    el("span", { class: "dt-v " + (cls || "") }, val));
  box.appendChild(kv("Offer", couponSummary(c), "hl-offer"));
  box.appendChild(kv("Eligibility",
    v.eligible ? "✓ eligible" : `✗ ${v.reasons[0] || v.blockedLayer}`,
    v.eligible ? "hl-ok" : "hl-bad"));
  box.appendChild(kv("Pickup", pfTag(p.pass_form)));
  const rr = p.residency_restriction;
  box.appendChild(kv("Residency",
    rr && rr.restricted ? `${rr.restricted}${rr.scope ? ` · ${rr.scope}` : ""}` : "—",
    rr && rr.restricted === "yes" ? "hl-warn" : ""));
  if (STATE.visitDate) box.appendChild(kv("Availability " + STATE.visitDate.toISOString().slice(0, 10), cell.avail,
    cell.avail === "available" ? "hl-ok" : (cell.avail === "booked" || cell.avail === "closed") ? "hl-bad" : ""));
  if (c?.audience_policies?.length) {
    const pol = el("div", { class: "dt-pol" });
    for (const ap of c.audience_policies)
      pol.appendChild(el("div", {}, el("span", { class: "dt-aud" }, ap.audience + ": "), couponSummary({ audience_policies: [ap] })));
    box.appendChild(kv("By audience", pol));
  }
  const srcText = buildSourceText(cell, attr);
  box.appendChild(el("div", { class: "dt-srchead" }, "Source text"));
  box.appendChild(el("pre", { class: "src-text" }, srcText || "no source text recorded"));

  const note = el("div", { class: "dt-note", hidden: "hidden" });
  const planNote = (msg) => { note.textContent = msg; note.hidden = false; };
  const foot = el("div", { class: "dt-foot" });
  foot.appendChild(p.source_url
    ? el("a", { class: "btn-tiny primary", href: p.source_url, target: "_blank", rel: "noopener" }, "预定 ↗")
    : el("span", { class: "hint" }, "no booking link"));
  const copyBtn = el("button", { class: "btn-tiny" }, "复制原文");
  copyBtn.addEventListener("click", () => navigator.clipboard.writeText(srcText).then(() => {
    copyBtn.textContent = "已复制 ✓"; setTimeout(() => copyBtn.textContent = "复制原文", 1200);
  }));
  foot.appendChild(copyBtn);
  foot.appendChild(el("button", { class: "btn-tiny", onclick: async () => {
    await auditPut(buildRecord({ kind:"pass",
      id:`${cell.lib.id}__${cell.pass.attraction_rawslug}`, field:"_verdict", status:"verified_ok" }));
    planNote("已记录：通过审查 ✓"); renderMatrix();
  } }, "通过审查"));
  foot.appendChild(el("button", { class: "btn-tiny", onclick: () => openAuditForm(cell, attr) }, "修改数据"));
  box.appendChild(foot);
  box.appendChild(note);
  openModal(`${attr.name} × ${cell.lib.town}`, box);
}

// ─────────────────────────────────────────────
//  AUDIT FORM EDITOR (openAuditForm) — redesigned
//  顺序：为什么改 → 改哪项 → 改成什么 → 备注 → 保存
// ─────────────────────────────────────────────

// Chinese label maps for the redesigned audit form
const ZH = {
  card_eligibility: {
    ma_resident: "全 MA 居民可办",
    town_resident: "仅本镇居民",
    town_or_works: "本镇居民或在本镇工作",
    network: "本联盟内",
    none: "无限制",
    unknown: "未知",
  },
  pass_pickup_default: {
    same_as_card: "同办卡资格",
    ma_resident: "全 MA 居民",
    town_resident: "仅本镇",
    town_cardholder_only: "仅本馆持卡人",
    network: "本联盟内",
    walkin_for_nonresidents: "非居民当天到馆",
    none: "无限制",
    unknown: "未知",
  },
  coupon_form: {
    free: "免费",
    "percent-off": "百分比折扣",
    "dollar-off": "固定减免",
    "per-person-price": "持卡固定价",
    bogo: "买一送一",
    discount: "笼统折扣（未注明）",
  },
  pass_form: {
    digital_email: "电子券（邮件）",
    physical_coupon: "到馆取券",
    physical_circ: "取券并归还",
  },
  residency_restricted: {
    yes: "有居住限制",
    no: "无限制",
    unknown: "未知",
  },
  residency_scope: {
    town: "仅本镇",
    ma: "全 MA",
  },
  visitor_residency: {
    ma_resident: "仅 MA 居民可入",
    town_resident: "仅本镇居民",
    none: "无限制",
    unknown: "未知",
  },
  reservation_required: {
    none: "无需预约",
    timed_entry: "需预约时段",
    walk_in_ok: "可直接进",
  },
};

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

  wrap.appendChild(el("div", { class: "ro-head" }, "图书馆 · " + cell.lib.town));
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
  for (const code of ASPECTS)
    aspectRow.appendChild(el("label", { class: "af-aspect" },
      el("input", { type: "checkbox", name: "af-aspect", value: code }), " " + (ASPECT_ZH[code] || code)));
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

  openModal(`修改数据：${attr.name} × ${cell.lib.town}`, form);
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

  // restore the operator's last filters/display from localStorage (survive refresh)
  const saved = loadPanelState();
  if (saved) {
    if (Array.isArray(saved.libs)) STATE.selectedLibs = new Set(saved.libs);
    if (Array.isArray(saved.attrs)) STATE.selectedAttrs = new Set(saved.attrs);
    if (typeof saved.onlyEligible === "boolean") STATE.onlyEligible = saved.onlyEligible;
    if (typeof saved.onlyInStock === "boolean") STATE.onlyInStock = saved.onlyInStock;
    if (typeof saved.showStock === "boolean") STATE.showStock = saved.showStock;
    if (saved.display) Object.assign(STATE.display, saved.display);
    if (saved.zip) STATE.homeZip = saved.zip;
    if (saved.date) { STATE.visitDate = new Date(saved.date + "T00:00:00Z"); dateInput.value = saved.date; }
  }
  $("#home-zip").value = STATE.homeZip;
  $("#opt-only-eligible").checked = STATE.onlyEligible;
  $("#opt-only-instock").checked = STATE.onlyInStock;
  $("#opt-show-stock").checked = STATE.showStock;

  renderCardList();
  updateLibCount();
  renderAttrList(); updateAttrCount();

  // modal close: × button, click outside the card, or Esc
  $("#mx-modal-close").onclick = closeModal;
  $("#mx-modal").onclick = (e) => { if (e.target.id === "mx-modal") closeModal(); };
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModal(); });
  STATE.audits = await auditLoadAll();
  renderMatrix();
  initAuditSystem();

  // Attr filter controls
  $("#btn-attr-all").onclick = () => { STATE.selectedAttrs = new Set(STATE.attractions.map(a=>a.slug)); renderAttrList(); updateAttrCount(); renderMatrix(); };
  $("#btn-attr-none").onclick = () => { STATE.selectedAttrs = new Set(); renderAttrList(); updateAttrCount(); renderMatrix(); };
  $("#attr-search").oninput = (e) => { STATE.attrSearch = e.target.value; renderAttrList(); };
  $("#opt-only-eligible").onchange = (e) => { STATE.onlyEligible = e.target.checked; renderMatrix(); };
  $("#opt-only-instock").onchange = (e) => { STATE.onlyInStock = e.target.checked; renderMatrix(); };
  $("#opt-show-stock").onchange = (e) => { STATE.showStock = e.target.checked; renderMatrix(); };
  for (const [key, id] of Object.entries({policies:"d-policies",verdict:"d-verdict",pickup:"d-pickup",avail:"d-avail",distance:"d-distance",restrict:"d-restrict",warn:"d-warn"})) {
    $("#"+id).checked = !!STATE.display[key];
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
//  AUDIT SYSTEM — count badge + disk-path helper
// ─────────────────────────────────────────────

function auditUpdateCount() {
  const n = Object.keys(STATE.audits || {}).length;
  const badge = document.getElementById("audit-count");
  if (badge) badge.textContent = String(n);
}

// On-disk applying path for a given kind/id/field.
// Returns null for pass kind (raw-slug keying mismatch — cannot auto-apply).
function auditDiskPath(kind, id, field) {
  if (kind === "pass") return null;
  const kindDir = { library: "libraries", attraction: "attractions", branch: "branches" }[kind] || kind + "s";
  return `data/overrides/${kindDir}/${id}/${field}.json`;
}

// Human-readable note shown for pass records in the audit log.
const PASS_INFO_NOTE = "信息性标注（不参与构建合并；pass 纠错需用 raw slug 手工处理）";

// ── Audit Log ─────────────────────────────────

function auditRenderLog(showPaths) {
  const listEl = document.getElementById("audit-log-list");
  if (!listEl) return;
  listEl.innerHTML = "";

  let entries = Object.values(STATE.audits || {});

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
    const emoji = { corrected: "✏️", reviewed: "✅", noted: "📝", feedback: "💬" }[record.status] || "";
    right.appendChild(el("span", { class: "ale-auditor" }, emoji + " " + (record.audited_by || "")));
    right.appendChild(el("span", { class: "ale-time" }, record.audited_at ? record.audited_at.slice(0, 19).replace("T", " ") : "—"));
    const delBtn = el("button", { class: "btn-tiny", style: "font-size:10px;color:var(--rd);border-color:var(--rd)" }, "撤销");
    delBtn.addEventListener("click", async () => {
      if (confirm(`撤销记录: ${record.target}?`)) {
        await auditRevoke(record.target);
        auditUpdateCount();
        auditRenderLog();
        renderMatrix();
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
  auditRenderLog();

  // Export button
  document.getElementById("btn-export-audits").onclick = () => {
    const blob = new Blob([JSON.stringify(STATE.audits || {}, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = "audit_overrides.json"; a.click();
    URL.revokeObjectURL(a.href);
  };

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
