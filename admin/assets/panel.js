// MuseumPapa Admin Panel — rebuilt on new data shapes + funnel engine
// Edit source under admin/ only. See web/sync-admin.mjs for copy rules.

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
  branchesByLib: {},  // library_id -> Branch[]
  MA_ZIPS: new Set(),
  // derived
  networks: [],
  libsByNetwork: {},
  selectedNetworks: new Set(),
  selectedLibs: new Set(),   // derived from selectedNetworks
  // controls
  homeZip: DEFAULT_ZIP,
  homeGeo: null,
  visitDate: null,     // Date object or null
  showOnlyCovered: true,
  categoryFilter: "",
  activeLens: "A",
  // group collapse state: net -> bool collapsed
  groupCollapsed: {},
};

// Re-derive STATE.selectedLibs from STATE.selectedNetworks.
function syncSelectedLibs() {
  STATE.selectedLibs = new Set(
    STATE.libs
      .filter(l => STATE.selectedNetworks.has(l.network || "Unknown"))
      .map(l => l.id)
  );
}

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
    fetchJson("/data/structured/town_zips.json"),
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

  STATE.passesByAttr = {};
  for (const p of STATE.passes) {
    (STATE.passesByAttr[p.attraction_slug] ||= []).push(p);
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

  // Default: all networks selected
  STATE.selectedNetworks = new Set(STATE.networks);
  syncSelectedLibs();
}

// ─────────────────────────────────────────────
//  FUNNEL ENGINE  (mirrors web/src/lib/engine.ts exactly)
// ─────────────────────────────────────────────
function isMaZip(zip) { return STATE.MA_ZIPS.has(zip); }

function checkL1Card(lib, heldLibraryIds) {
  if (heldLibraryIds.includes(lib.id)) return { ok: true };
  const nets = new Set(heldLibraryIds.map(id => STATE.libsById[id]?.network).filter(Boolean));
  if (nets.has(lib.network)) return { ok: true };
  return { ok: false, reason: `无 ${lib.network} 网络的卡` };
}

function checkL3Residency(rr, lib, homeZip) {
  if (!rr || rr.restricted === "no") return { ok: true };
  if (rr.restricted === "unknown") return { ok: true, warn: true, reason: "取 pass 资格未确认" };
  if (rr.scope === "town") return lib.resident_zips.includes(homeZip) ? { ok: true } : { ok: false, reason: `${lib.town} 仅本镇居民可取` };
  if (rr.scope === "ma") return isMaZip(homeZip) ? { ok: true } : { ok: false, reason: "仅 MA 居民可取" };
  return { ok: true, warn: true };
}

function checkL4VisitorResidency(ve, homeZip) {
  if (!ve || ve.residency === "none") return { ok: true };
  if (ve.residency === "unknown") return { ok: true, warn: true, reason: "景点访客资格未确认" };
  if (ve.residency === "ma_resident") return isMaZip(homeZip) ? { ok: true } : { ok: false, reason: "景点仅 MA 居民可入" };
  return { ok: true, warn: true, reason: `景点可能仅 ${ve.scope ?? "本镇"} 居民` };
}

const WD = ["sundays", "mondays", "tuesdays", "wednesdays", "thursdays", "fridays", "saturdays"];
function checkL8Restrictions(r, date) { // date: Date; USE UTC getters
  if (!r) return { ok: true };
  const m = date.getUTCMonth() + 1, d = date.getUTCDate(), dow = date.getUTCDay();
  for (const b of r.blackout) if (b.month === m && (b.day == null || b.day === d)) return { ok: false, reason: "blackout" };
  if (r.blackout_recurring.includes(WD[dow])) return { ok: false, reason: "该星期几不可用" };
  if (r.weekdays_only && (dow === 0 || dow === 6)) return { ok: false, reason: "仅平日" };
  if (r.seasonal) {
    const { start_month: s, end_month: e } = r.seasonal;
    const inS = s <= e ? (m >= s && m <= e) : (m >= s || m <= e);
    if (!inS) return { ok: false, reason: "季节性闭区" };
  }
  return { ok: true };
}

function checkL10Availability(av, iso) {
  const s = av?.[iso];
  if (s === "available") return { ok: true };
  if (s == null) return { ok: true, warn: true, reason: "该日库存未知" };
  return { ok: false, reason: s === "booked" ? "该日已订满" : "该日不可预约" };
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

const STRENGTH = { free: 6, "percent-off": 5, "dollar-off": 4, "per-person-price": 3, discount: 2, bogo: 1 };
function couponStrength(f) { return STRENGTH[f] ?? 0; }
function passStrength(c) {
  if (!c || !c.audience_policies.length) return 0;
  return Math.max(...c.audience_policies.map(p => couponStrength(p.form)));
}
function couponSummary(c) {
  if (!c) return "优惠详情未知";
  if (c.summary) return c.summary;
  const p = c.audience_policies[0];
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
  physical_circ: { label: "借还", cls: "pill-borrow" },
  physical_coupon: { label: "凭证", cls: "pill-pickup" },
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
    const cardEl = el("div", { class: "card-group" });
    const hdr = el("label", { class: "card-header" },
      el("input", {
        type: "checkbox",
        ...(STATE.selectedNetworks.has(net) ? { checked: "checked" } : {}),
        onchange: (e) => {
          if (e.target.checked) STATE.selectedNetworks.add(net);
          else STATE.selectedNetworks.delete(net);
          syncSelectedLibs();
          renderCardList(); updateLibCount(); renderLens();
        },
      }),
      el("span", { class: "card-name" }, net),
      el("span", { class: "card-count" }, `${libs.length} 馆`),
    );
    cardEl.appendChild(hdr);
    const members = el("div", { class: "card-members" });
    for (const l of libs) {
      const elig = l.card_eligibility || "unknown";
      members.appendChild(el("div", { class: "card-member" },
        el("span", { class: "card-member-name" },
          l.name.replace(/\sPublic Library$|\sLibrary$/, "")),
        eligTag(elig),
      ));
    }
    cardEl.appendChild(members);
    wrap.appendChild(cardEl);
  }
}

function updateLibCount() {
  $("#lib-count").textContent = `${STATE.selectedNetworks.size} / ${STATE.networks.length}`;
}

function renderCategoryFilter() {
  const cats = new Set();
  for (const a of STATE.attractions) (a.categories || []).forEach(c => cats.add(c));
  const sel = $("#opt-category");
  for (const c of [...cats].sort()) sel.appendChild(el("option", { value: c }, c));
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
    const libPasses = STATE.passes.filter(p => p.library_id === lib.id);
    for (const pass of libPasses) {
      const attr = STATE.attrBySlug[pass.attraction_slug];
      if (STATE.categoryFilter && !(attr?.categories || []).includes(STATE.categoryFilter)) continue;
      const verdict = resolvePass(pass, lib, attr, user, date);
      if (STATE.showOnlyCovered && !verdict.eligible) continue;
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
    const libPasses = STATE.passes.filter(p => p.library_id === lib.id);

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
    case "A": table = buildLensA(); break;
    case "B": table = buildLensB(); break;
    case "C": table = buildLensC(); break;
    case "D": table = buildLensD(); break;
    default: table = el("div", {}, "Unknown lens");
  }
  container.appendChild(table);
  updateStat();
}

function updateStat() {
  const selCount = STATE.selectedLibs.size;
  const netCount = STATE.selectedNetworks.size;
  let summary = `${netCount} 张卡 · ${selCount} 馆 · ${STATE.attractions.length} 景`;
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
 * Returns the ISO string of the first date that:
 *   1. pass.availability[iso] === "available"  (not booked/closed/unknown)
 *   2. checkL8Restrictions(pass.restrictions, date) passes
 * Returns null if no such date exists within the window.
 */
function nextAvailableDay(pass, startDate) {
  const WINDOW = 90;
  const av = pass.availability || {};
  // start scanning from startDate itself (inclusive)
  const cur = new Date(startDate.getTime());
  for (let i = 0; i < WINDOW; i++) {
    const iso = cur.toISOString().slice(0, 10);
    if (av[iso] === "available") {
      const l8 = checkL8Restrictions(pass.restrictions, cur);
      if (l8.ok) return iso;
    }
    cur.setUTCDate(cur.getUTCDate() + 1);
  }
  return null;
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
      const nextDay = nextAvailableDay(pass, date);
      const nextEl = nextDay
        ? el("div", { class: "sim-next-avail" }, `下一可用日: ${nextDay}`)
        : el("div", { class: "sim-next-avail", style: "color:var(--rd);background:var(--rd-pale);border-color:var(--rd)" },
            "未来 90 天内无可用日");
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
  renderLens();
  initSimulator();

  // All / None
  $("#btn-all").addEventListener("click", () => {
    STATE.selectedNetworks = new Set(STATE.networks);
    syncSelectedLibs();
    renderCardList(); updateLibCount(); renderLens();
  });
  $("#btn-none").addEventListener("click", () => {
    STATE.selectedNetworks.clear();
    syncSelectedLibs();
    renderCardList(); updateLibCount(); renderLens();
  });

  // Lens tabs
  for (const btn of document.querySelectorAll(".lens-btn")) {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".lens-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      STATE.activeLens = btn.dataset.lens;
      renderLens();
    });
  }

  // Filters
  $("#opt-only-covered").addEventListener("change", (e) => { STATE.showOnlyCovered = e.target.checked; renderLens(); });
  $("#opt-category").addEventListener("change", (e) => { STATE.categoryFilter = e.target.value; renderLens(); });

  // Date
  dateInput.addEventListener("change", (e) => {
    const v = e.target.value;
    STATE.visitDate = v ? new Date(v + "T00:00:00Z") : null;
    renderLens();
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
    renderLens();
  }
  $("#btn-geocode").addEventListener("click", applyZip);
  $("#home-zip").addEventListener("keydown", (e) => { if (e.key === "Enter") applyZip(); });
  $("#home-zip").addEventListener("blur", () => {
    if (!($("#home-zip").value || "").trim()) $("#home-zip").value = DEFAULT_ZIP;
  });

  // Auto-apply default ZIP on load
  applyZip();
}

init().catch((e) => {
  console.error(e);
  $("#stat-summary").textContent = "加载错误: " + e.message;
  $("#lens-content").innerHTML = `<div class="loading-msg" style="color:var(--rd)">加载失败: ${e.message}</div>`;
});
