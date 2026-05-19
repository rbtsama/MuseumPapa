// MuseumPapa Admin Panel — interactive matrix viewer (libraries × attractions)
// Output format aligned with web/ frontend CouponLine + PassTypeLabel conventions.

const DEFAULT_ZIP = "01880";

const STATE = {
  libs: [], attractions: [], branches: {}, passes: [], passesByAttr: {},
  networks: [],          // ['NOBLE', 'Minuteman', ...] — used only for sidebar grouping
  libsByNetwork: {},
  selectedLibs: new Set(),
  homeGeo: null,
  showOnlyCovered: true,
  sortMode: "coverage-desc",
  categoryFilter: "",
};

// ---------- DOM helpers ----------
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

// Project geo objects use either `lng` (from zippopotam) or `lon`
// (from data/structured/*.json) — normalize both.
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
// Pickup point geo for a pass: branch geo if specified, else library geo.
// Digital passes don't need pickup — returns null.
function pickupGeo(pass) {
  if (pass.pickup_method === "digital") return null;
  const brs = (pass.pickup_branches || []).map(bid => STATE.branches[bid]).filter(Boolean);
  if (brs.length && brs[0].geo) return brs[0].geo;
  const lib = STATE.libs.find(l => l.id === pass.library_id);
  return lib?.geo || null;
}

// ---------- data load ----------
async function loadData() {
  const fetchJson = async (p) => {
    const r = await fetch(p);
    if (!r.ok) throw new Error(`${p} → ${r.status}`);
    return r.json();
  };
  // Served via web/'s Vite dev server (pnpm -C web dev) or Vercel — both expose
  // public/data/structured at the absolute /data/structured/ URL.
  const [libsD, attrsD, branchesD, passesD] = await Promise.all([
    fetchJson("/data/structured/libraries.json"),
    fetchJson("/data/structured/attractions.json"),
    fetchJson("/data/structured/branches.json"),
    fetchJson("/data/structured/passes.json"),
  ]);
  STATE.libs = libsD.libraries.slice().sort((a, b) => a.name.localeCompare(b.name));
  STATE.attractions = attrsD.attractions;
  for (const br of branchesD.branches) STATE.branches[br.id] = br;
  STATE.passes = passesD.passes;
  STATE.passesByAttr = {};
  for (const p of STATE.passes) (STATE.passesByAttr[p.attraction_slug] ||= []).push(p);

  // Group libs by network — used only for sidebar layout, not for filter logic.
  STATE.libsByNetwork = {};
  for (const l of STATE.libs) {
    const net = l.network || "Unknown";
    (STATE.libsByNetwork[net] ||= []).push(l);
  }
  STATE.networks = Object.keys(STATE.libsByNetwork).sort((a, b) =>
    (STATE.libsByNetwork[b].length - STATE.libsByNetwork[a].length) || a.localeCompare(b));
  // Default: all libraries selected; admin can trim.
  STATE.selectedLibs = new Set(STATE.libs.map(l => l.id));
}

// ---------- coupon formatting (mirrors web/src/components/CouponLine.tsx) ----------
function bucket(audience) {
  switch (audience) {
    case "Adult": case "Senior": return "Adult";
    case "Child": return "Child";
    case "Youth": return "Youth";
    case "Everyone": return "Everyone";
    case "Vehicle": case "Single ticket": return null;
    default: return null;
  }
}
function fmtAmount(p) {
  switch (p.form) {
    case "free": return "FREE";
    case "percent-off": return p.value != null ? `${p.value}% off` : "discount";
    case "dollar-off": return p.value != null ? `$${p.value} off` : "discount";
    case "per-person-price": return p.value != null ? `$${p.value}` : "discount";
    case "discount": return "discount";
    default: return p.form || "—";
  }
}
function isRedundantAge(b, audience, age) {
  if (!age) return true;
  const { min, max } = age;
  if (b === "Adult" && max == null && min != null && min >= 18 && min <= 19) return true;
  if (b === "Adult" && audience === "Senior") return true;
  if ((b === "Youth" || b === "Child") && min == null && max != null && max >= 17 && max <= 18) return true;
  if (b === "Youth" && min === 13 && max === 17) return true;
  return false;
}
function fmtAudienceLabel(p) {
  const b = bucket(p.audience);
  if (b == null) return null;
  const age = p.age_range;
  if (!age || isRedundantAge(b, p.audience, age)) return b;
  const { min, max } = age;
  if (min != null && max != null) return `age ${min}-${max}`;
  if (max != null) return `age<${max + 1}`;
  if (min != null) return `age ${min}+`;
  return b;
}
function formatCapacity(cap) {
  if (!cap || cap.n == null || cap.n <= 0) return null;
  if (cap.kind === "people" || cap.kind === "ticket") return `up to ${cap.n}`;
  return null;
}
function isNonAdmission(coupon) {
  if (coupon?.capacity?.kind === "vehicle") return true;
  return (coupon?.audience_policies || []).some(p => p.audience === "Vehicle");
}

function renderCouponLine(coupon) {
  if (!coupon?.audience_policies?.length) return el("div", { class: "cell-prices" }, "—");
  if (isNonAdmission(coupon)) {
    return el("div", { class: "cell-prices" }, el("span", { class: "amount" }, "Parking Discount"));
  }
  const wrap = el("div", { class: "cell-prices" });
  coupon.audience_policies.forEach((p, i) => {
    if (i > 0) wrap.appendChild(el("span", { class: "sep" }, "·"));
    const label = fmtAudienceLabel(p);
    if (label && label !== "Everyone") wrap.appendChild(el("span", { class: "label" }, label + " "));
    wrap.appendChild(el("span", { class: "amount" }, fmtAmount(p)));
  });
  return wrap;
}

// ---------- pass-type pill ----------
const PASS_TYPE_META = {
  "digital":         { label: "Email",  cls: "pill-email" },
  "physical-coupon": { label: "Pickup", cls: "pill-pickup" },
  "physical-circ":   { label: "Pik&Rtn", cls: "pill-borrow" },
  "unknown":         { label: "Pass",   cls: "pill-unknown" },
};
function passTypePill(t) {
  const m = PASS_TYPE_META[t] || PASS_TYPE_META.unknown;
  return el("span", { class: `pill ${m.cls}` }, m.label);
}

// ---------- BEST ranking ----------
function couponStrength(pass, attraction) {
  if (!pass) return -1;
  const pols = pass.coupon?.audience_policies || [];
  let s = 0;
  for (const p of pols) {
    if (p.form === "free") s = Math.max(s, 1000);
    else if (p.form === "percent-off") s = Math.max(s, p.value || 0);
    else if (p.form === "dollar-off") s = Math.max(s, (p.value || 0) * 2);
    else if (p.form === "per-person-price") {
      const orig = attraction?.original_price?.age_pricing?.adult?.price;
      if (orig && p.value < orig) s = Math.max(s, ((orig - p.value) / orig) * 100);
    } else if (p.form === "discount") s = Math.max(s, p.value || 0);
  }
  return s;
}
function bestPassFor(attraction) {
  const candidates = (STATE.passesByAttr[attraction.slug] || []).filter(p => STATE.selectedLibs.has(p.library_id));
  if (!candidates.length) return null;
  let best = candidates[0], bestScore = couponStrength(best, attraction);
  for (const p of candidates.slice(1)) {
    const s = couponStrength(p, attraction);
    if (s > bestScore) { best = p; bestScore = s; }
  }
  return best;
}

// ---------- pickup location label (mirrors web/ CouponRow logic) ----------
function locationLabel(pass) {
  const lib = STATE.libs.find(l => l.id === pass.library_id);
  if (!lib) return pass.library_id;
  if (pass.pickup_method === "digital") return lib.name;
  const brs = (pass.pickup_branches || []).map(bid => STATE.branches[bid]).filter(Boolean);
  if (brs.length > 1) return `${lib.town} · ${brs.length} branches`;
  if (brs.length === 1 && brs[0].id !== `${lib.id}--main`) return brs[0].name;
  return lib.town;
}

// ---------- restrictions summary ----------
function hasRestrictions(pass) {
  const r = pass.restrictions;
  if (!r) return false;
  return Object.entries(r).some(([k, v]) =>
    v != null && v !== false && (!Array.isArray(v) || v.length > 0));
}
function restrictionLabel(pass) {
  const r = pass.restrictions || {};
  const bits = [];
  if (r.blackout_dates?.length) bits.push("blackout");
  if (r.weekdays_only) bits.push("weekdays only");
  if (r.seasonal) bits.push(`seasonal: ${r.seasonal}`);
  if (r.reservation_required) bits.push("reservation");
  if (r.lead_time_days) bits.push(`${r.lead_time_days}d lead`);
  if (r.hold_period_days) bits.push(`${r.hold_period_days}d hold`);
  return bits.length ? bits.join(" · ") : "with restrictions";
}

// ---------- cell render ----------
function renderCell(pass, attraction, opts = {}) {
  if (!pass) return el("div", { class: "cell-empty" }, "—");
  const cls = "cell" + (opts.best ? " best" : "");
  const bookBtn = el("button", {
    class: "book-btn", type: "button",
    onclick: () => {
      if (pass.source_url) window.open(pass.source_url, "_blank", "noopener,noreferrer");
    },
  }, "Book →");
  // For physical passes, append distance from home -> pickup point next to location.
  // Digital ('Email') passes don't need pickup, so no distance line.
  let locNode;
  if (pass.pickup_method !== "digital") {
    const pg = pickupGeo(pass);
    const pickupDist = STATE.homeGeo && pg ? haversineMi(STATE.homeGeo, pg) : null;
    locNode = el("div", { class: "cell-loc" },
      locationLabel(pass),
      pickupDist != null ? el("span", { class: "dist" }, ` · ${Math.round(pickupDist)} mi`) : null,
    );
  } else {
    locNode = el("div", { class: "cell-loc" }, locationLabel(pass));
  }
  return el("div", { class: cls },
    passTypePill(pass.pass_type),
    renderCouponLine(pass.coupon),
    locNode,
    (() => {
      const cap = formatCapacity(pass.coupon?.capacity);
      return cap ? el("div", { class: "cell-cap" }, cap) : null;
    })(),
    hasRestrictions(pass) ? el("div", { class: "cell-restr" }, restrictionLabel(pass)) : null,
    bookBtn,
  );
}

// ---------- attraction price tiers (mirrors web/src/components/AttractionInfoRows.tsx) ----------
function fmtMoney(v) {
  if (v == null) return "";
  if (v === 0) return "FREE";
  if (Number.isInteger(v)) return `$${v}`;
  return `$${v.toFixed(2)}`;
}
function buildPriceTiers(attraction) {
  const op = attraction.original_price || {};
  const ap = op.age_pricing || {};
  const ip = op.identity_pricing || {};
  const adult   = ap.adult?.price   ?? null;
  const youth   = ap.youth?.price   ?? null;
  const child   = ap.child?.price   ?? null;
  const senior  = ap.senior?.price  ?? null;
  const student = ip.student?.price ?? null;
  const educator= ip.educator?.price?? null;
  const military= ip.military?.price?? null;
  const freeUnder = ap.free_under_age ?? null;
  const tiers = [];
  if (adult   != null) tiers.push({ label: "adult",  value: adult  });
  if (senior  != null && senior  !== adult) tiers.push({ label: "senior",  value: senior });
  if (youth   != null && youth   !== adult) tiers.push({ label: "youth",   value: youth });
  if (child   != null && child   !== adult) {
    const lbl = freeUnder != null ? `age ${freeUnder}+` : "child";
    tiers.push({ label: lbl, value: child });
  }
  if (student != null && student !== adult) tiers.push({ label: "student", value: student });
  if (educator!= null && educator!== adult) tiers.push({ label: "educator", value: educator });
  if (military!= null && military!== adult) tiers.push({ label: "military", value: military });
  return { tiers, freeUnder };
}
function renderPriceTiers(attraction) {
  const { tiers, freeUnder } = buildPriceTiers(attraction);
  if (!tiers.length && freeUnder == null) return null;
  const out = el("div", { class: "price-tiers" });
  tiers.forEach((t, i) => {
    if (i > 0) out.appendChild(el("span", { class: "sep" }, "·"));
    if (tiers.length > 1) out.appendChild(el("span", { class: "label" }, t.label));
    out.appendChild(el("span", { class: "val" }, fmtMoney(t.value)));
  });
  if (freeUnder != null) {
    if (tiers.length) out.appendChild(el("span", { class: "sep" }, "·"));
    out.appendChild(el("span", { class: "label" }, `age <${freeUnder}`));
    out.appendChild(el("span", { class: "val" }, "FREE"));
  }
  return out;
}

// ---------- sidebar render — cards (= networks) ----------
const ELIG_LABEL = {
  "open_ma_resident": "open MA",
  "residents_only": "residents only",
  "network_only": "network only",
  "unknown": "unknown",
};
const ELIG_CLASS = {
  "open_ma_resident": "elig-open",
  "residents_only": "elig-residents",
  "network_only": "elig-network",
  "unknown": "elig-unknown",
};

function renderCardList() {
  const wrap = $("#lib-list");
  const q = ($("#lib-filter").value || "").toLowerCase();
  wrap.innerHTML = "";
  for (const net of STATE.networks) {
    const libs = STATE.libsByNetwork[net].filter(l =>
      !q || l.name.toLowerCase().includes(q) || l.id.includes(q) || (l.town || "").toLowerCase().includes(q));
    if (!libs.length) continue;
    // Network header — pure visual grouping. Includes Select/Clear-all-in-group
    // helpers for convenience; not itself a filter.
    const selInGroup = libs.filter(l => STATE.selectedLibs.has(l.id)).length;
    const cardEl = el("div", { class: "card-group" });
    const hdr = el("div", { class: "card-header" },
      el("span", { class: "card-name" }, net),
      el("span", { class: "card-count" }, `${selInGroup} / ${libs.length}`),
      el("button", { class: "btn-mini", type: "button",
        onclick: () => { libs.forEach(l => STATE.selectedLibs.add(l.id));
          renderCardList(); updateLibCount(); renderMatrix(); } }, "all"),
      el("button", { class: "btn-mini", type: "button",
        onclick: () => { libs.forEach(l => STATE.selectedLibs.delete(l.id));
          renderCardList(); updateLibCount(); renderMatrix(); } }, "none"),
    );
    cardEl.appendChild(hdr);
    const members = el("div", { class: "card-members" });
    for (const l of libs) {
      const elig = l.eligibility || "unknown";
      members.appendChild(el("label", { class: "card-member" },
        el("input", {
          type: "checkbox",
          ...(STATE.selectedLibs.has(l.id) ? { checked: "checked" } : {}),
          onchange: (e) => {
            if (e.target.checked) STATE.selectedLibs.add(l.id);
            else STATE.selectedLibs.delete(l.id);
            renderCardList(); updateLibCount(); renderMatrix();
          },
        }),
        el("span", { class: "card-member-name" },
          l.name.replace(/\sPublic Library$|\sLibrary$/, "")),
        el("span", { class: `elig-tag ${ELIG_CLASS[elig]}` }, ELIG_LABEL[elig]),
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
  for (const c of [...cats].sort()) sel.appendChild(el("option", { value: c }, c));
}

// ---------- sort + filter ----------
function sortedVisible() {
  let list = STATE.attractions.slice();
  if (STATE.categoryFilter) list = list.filter(a => (a.categories || []).includes(STATE.categoryFilter));
  list.sort((a, b) => {
    if (STATE.sortMode === "name-asc") return a.museum_name.localeCompare(b.museum_name);
    if (STATE.sortMode === "coverage-desc") {
      const ca = (STATE.passesByAttr[a.slug] || []).filter(p => STATE.selectedLibs.has(p.library_id)).length;
      const cb = (STATE.passesByAttr[b.slug] || []).filter(p => STATE.selectedLibs.has(p.library_id)).length;
      return cb - ca || a.museum_name.localeCompare(b.museum_name);
    }
    if (STATE.sortMode === "best-strength") {
      const sa = couponStrength(bestPassFor(a), a);
      const sb = couponStrength(bestPassFor(b), b);
      return sb - sa || a.museum_name.localeCompare(b.museum_name);
    }
    if (STATE.sortMode === "price-desc") {
      const pa = a.original_price?.age_pricing?.adult?.price || 0;
      const pb = b.original_price?.age_pricing?.adult?.price || 0;
      return pb - pa || a.museum_name.localeCompare(b.museum_name);
    }
    if (STATE.sortMode === "distance-asc") {
      if (!STATE.homeGeo) return 0;
      const da = a.geo ? haversineMi(STATE.homeGeo, a.geo) ?? 1e9 : 1e9;
      const db = b.geo ? haversineMi(STATE.homeGeo, b.geo) ?? 1e9 : 1e9;
      return da - db;
    }
    return 0;
  });
  return list;
}

// ---------- main matrix render ----------
function renderMatrix() {
  const thead = $("#matrix-head");
  const tbody = $("#matrix-body");
  thead.innerHTML = ""; tbody.innerHTML = "";

  const selLibs = STATE.libs.filter(l => STATE.selectedLibs.has(l.id));

  thead.appendChild(el("th", { class: "attr-col" }, "Attraction"));
  for (const l of selLibs) {
    const short = l.name.replace(/\sPublic Library$/, "").replace(/\sLibrary$/, "");
    const elig = l.eligibility || "unknown";
    thead.appendChild(el("th", {},
      el("div", {}, short),
      el("div", { class: "th-meta" },
        el("span", { class: "th-net" }, l.network || "?"),
        el("span", { class: `elig-tag ${ELIG_CLASS[elig]}` }, ELIG_LABEL[elig]),
      ),
    ));
  }

  const attrs = sortedVisible();
  const rows = [];
  for (const a of attrs) {
    // For each row, compute best pass index among visible selLibs.
    // Tie-break: first (leftmost) library wins.
    const cells = selLibs.map(l => (STATE.passesByAttr[a.slug] || []).find(p => p.library_id === l.id) || null);
    let bestIdx = -1, bestScore = -1;
    cells.forEach((p, i) => {
      if (!p) return;
      const s = couponStrength(p, a);
      if (s > bestScore) { bestScore = s; bestIdx = i; }
    });
    if (STATE.showOnlyCovered && bestIdx < 0) continue;
    rows.push({ a, cells, bestIdx });
  }

  for (const { a, cells, bestIdx } of rows) {
    const tr = el("tr");
    const origPrice = a.original_price?.age_pricing?.adult?.price;
    const dist = STATE.homeGeo && a.geo ? haversineMi(STATE.homeGeo, a.geo) : null;

    // Attraction column — thumbnail + serif name + price + distance + categories
    // hero_image is { og_image_url, local_path } where local_path looks like
    // "static/images/boston-childrens-museum.png" — strip to filename and serve
    // from web/public/images (the same dir Vercel deploys).
    const localPath = a.hero_image?.local_path;
    const fileName = localPath ? localPath.split("/").pop() : null;
    const heroSrc = fileName ? `/images/${fileName}` : null;
    let thumb;
    if (heroSrc) {
      thumb = el("img", { class: "attr-thumb", src: heroSrc, alt: "" });
      thumb.onerror = () => { thumb.style.display = "none"; };
    } else {
      thumb = el("div", { class: "attr-thumb attr-thumb-fallback" }, "—");
    }
    const cats = (a.categories || []).slice(0, 3).map(c => el("span", { class: "attr-cat" }, c));
    const town = a.address?.city || null;
    const resv = a.museum_reservation?.required;
    tr.appendChild(el("td", { class: "attr-col" },
      el("div", { class: "attr-row" },
        thumb,
        el("div", {},
          el("span", { class: "attr-name" }, a.museum_name),
          el("span", { class: "attr-meta" },
            town || "—",
            dist != null ? el("span", { class: "dist-tag" }, ` · ${Math.round(dist)} mi`) : null,
          ),
          renderPriceTiers(a),
          resv ? el("div", {}, el("span", { class: "resv-flag" }, "Reservation required")) : null,
          cats.length ? el("div", { class: "attr-categories" }, cats) : null,
        ),
      ),
    ));

    cells.forEach((p, i) => {
      tr.appendChild(el("td", {}, renderCell(p, a, { best: i === bestIdx })));
    });
    tbody.appendChild(tr);
  }

  // stat
  const covered = rows.filter(r => r.bestIdx >= 0).length;
  const free = rows.filter(r => {
    if (r.bestIdx < 0) return false;
    const p = r.cells[r.bestIdx];
    return (p.coupon?.audience_policies || []).some(pol => pol.form === "free");
  }).length;
  $("#stat-summary").textContent =
    `${STATE.selectedLibs.size} cards · ${covered}/${STATE.attractions.length} attractions covered · ${free} FREE`
    + (STATE.homeGeo ? ` · home ${STATE.homeGeo.zip}` : "");
}

// ---------- ZIP geocoding via zippopotam.us ----------
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

// ---------- wire-up ----------
async function init() {
  await loadData();
  renderCardList();
  updateLibCount();
  renderCategoryFilter();
  renderMatrix();

  $("#btn-all").addEventListener("click", () => {
    STATE.selectedLibs = new Set(STATE.libs.map(l => l.id));
    renderCardList(); updateLibCount(); renderMatrix();
  });
  $("#btn-none").addEventListener("click", () => {
    STATE.selectedLibs.clear();
    renderCardList(); updateLibCount(); renderMatrix();
  });
  $("#lib-filter").addEventListener("input", renderCardList);
  $("#opt-only-covered").addEventListener("change", (e) => { STATE.showOnlyCovered = e.target.checked; renderMatrix(); });
  $("#opt-sort").addEventListener("change", (e) => { STATE.sortMode = e.target.value; renderMatrix(); });
  $("#opt-category").addEventListener("change", (e) => { STATE.categoryFilter = e.target.value; renderMatrix(); });

  async function applyZip() {
    const input = $("#home-zip");
    const hint = $("#zip-hint");
    let zip = (input.value || "").trim();
    if (!/^\d{5}$/.test(zip)) {
      zip = DEFAULT_ZIP;
      input.value = DEFAULT_ZIP;
      hint.textContent = `ZIP cannot be empty; restored default ${DEFAULT_ZIP}.`;
      hint.className = "hint warn";
    } else {
      hint.textContent = "Resolving…"; hint.className = "hint";
    }
    try {
      STATE.homeGeo = await geocodeZip(zip);
      hint.textContent = `${STATE.homeGeo.name} (${STATE.homeGeo.lat.toFixed(3)}, ${STATE.homeGeo.lng.toFixed(3)})`;
      hint.className = "hint ok";
      renderMatrix();
    } catch (e) {
      hint.textContent = `Failed: ${e.message}`; hint.className = "hint warn";
    }
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
  $("#stat-summary").textContent = "load error: " + e.message;
});
