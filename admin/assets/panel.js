// MuseumPapa Admin Panel — interactive matrix viewer (libraries × attractions)
// Output format aligned with web/ frontend CouponLine + PassTypeLabel conventions.

const DEFAULT_ZIP = "01880";
const CARDS_LSKEY = "admin:cards";

const STATE = {
  libs: [], attractions: [], branches: {}, passes: [], passesByAttr: {},
  selectedLibs: new Set(),
  homeGeo: null,
  showOnlyCovered: true,
  sortMode: "coverage-desc",
  categoryFilter: "",
  cards: {},  // libId -> barcode string
};

function loadCards() {
  try { STATE.cards = JSON.parse(localStorage.getItem(CARDS_LSKEY) || "{}"); }
  catch { STATE.cards = {}; }
}
function saveCards(obj) {
  STATE.cards = obj;
  localStorage.setItem(CARDS_LSKEY, JSON.stringify(obj));
}

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

function haversineMi(a, b) {
  if (!a || !b) return null;
  const R = 3958.8, rad = (x) => x * Math.PI / 180;
  const dLat = rad(b.lat - a.lat), dLng = rad(b.lng - a.lng);
  const s = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(s));
}

// ---------- data load ----------
async function loadData() {
  const fetchJson = async (p) => {
    const r = await fetch(p);
    if (!r.ok) throw new Error(`${p} → ${r.status}`);
    return r.json();
  };
  const [libsD, attrsD, branchesD, passesD] = await Promise.all([
    fetchJson("../data/structured/libraries.json"),
    fetchJson("../data/structured/attractions.json"),
    fetchJson("../data/structured/branches.json"),
    fetchJson("../data/structured/passes.json"),
  ]);
  STATE.libs = libsD.libraries.slice().sort((a, b) => a.name.localeCompare(b.name));
  STATE.attractions = attrsD.attractions;
  for (const br of branchesD.branches) STATE.branches[br.id] = br;
  STATE.passes = passesD.passes;
  STATE.passesByAttr = {};
  for (const p of STATE.passes) (STATE.passesByAttr[p.attraction_slug] ||= []).push(p);
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
  "physical-circ":   { label: "Borrow", cls: "pill-borrow" },
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
  const cls = "cell" + (opts.best ? " best" : "") + (opts.nearest ? " nearest" : "");
  const bookBtn = el("button", {
    class: "book-btn", type: "button",
    onclick: (e) => { e.stopPropagation(); openBookModal(attraction, pass); },
  }, "Book →");
  return el("div", { class: cls, onclick: () => openDrawer(attraction, pass) },
    passTypePill(pass.pass_type),
    renderCouponLine(pass.coupon),
    el("div", { class: "cell-loc" }, locationLabel(pass)),
    (() => {
      const cap = formatCapacity(pass.coupon?.capacity);
      return cap ? el("div", { class: "cell-cap" }, cap) : null;
    })(),
    hasRestrictions(pass) ? el("div", { class: "cell-restr" }, restrictionLabel(pass)) : null,
    bookBtn,
  );
}

// ---------- sidebar render ----------
function renderLibList() {
  const wrap = $("#lib-list");
  const q = ($("#lib-filter").value || "").toLowerCase();
  wrap.innerHTML = "";
  for (const l of STATE.libs) {
    if (q && !l.name.toLowerCase().includes(q) && !l.id.includes(q)) continue;
    const lab = el("label", {},
      el("input", {
        type: "checkbox",
        ...(STATE.selectedLibs.has(l.id) ? { checked: "checked" } : {}),
        onchange: (e) => {
          if (e.target.checked) STATE.selectedLibs.add(l.id);
          else STATE.selectedLibs.delete(l.id);
          renderMatrix(); updateLibCount();
        },
      }),
      l.name
    );
    wrap.appendChild(lab);
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
    thead.appendChild(el("th", {}, short));
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

  // nearest 3 attractions by distance (highlight the BEST cell of those rows)
  let nearestSlugs = new Set();
  if (STATE.homeGeo) {
    const ranked = rows
      .filter(r => r.bestIdx >= 0 && r.a.geo?.lat != null)
      .map(r => ({ slug: r.a.slug, d: haversineMi(STATE.homeGeo, r.a.geo) }))
      .filter(x => x.d != null)
      .sort((x, y) => x.d - y.d)
      .slice(0, 3);
    nearestSlugs = new Set(ranked.map(x => x.slug));
  }

  for (const { a, cells, bestIdx } of rows) {
    const tr = el("tr");
    const origPrice = a.original_price?.age_pricing?.adult?.price;
    const dist = STATE.homeGeo && a.geo ? haversineMi(STATE.homeGeo, a.geo) : null;

    // Attraction column — thumbnail + serif name + price + distance + categories
    const heroSrc = a.hero_image ? `../web/public/images/${a.hero_image}` : null;
    const thumb = heroSrc
      ? el("img", { class: "attr-thumb", src: heroSrc, alt: "", onerror: "this.style.display='none'" })
      : el("div", { class: "attr-thumb attr-thumb-fallback" }, "—");
    const cats = (a.categories || []).slice(0, 3).map(c => el("span", { class: "attr-cat" }, c));
    tr.appendChild(el("td", { class: "attr-col" },
      el("div", { class: "attr-row" },
        thumb,
        el("div", {},
          el("span", { class: "attr-name" }, a.museum_name),
          el("span", { class: "attr-meta" },
            origPrice ? el("span", { class: "price-tag" }, `Adult $${origPrice}`) : "no price",
            dist != null ? el("span", { class: "dist-tag" }, ` · ${dist.toFixed(1)} mi`) : null,
          ),
          cats.length ? el("div", { class: "attr-categories" }, cats) : null,
        ),
      ),
    ));

    cells.forEach((p, i) => {
      const isBest = i === bestIdx;
      const isNear = isBest && nearestSlugs.has(a.slug);
      tr.appendChild(el("td", {}, renderCell(p, a, { best: isBest, nearest: isNear })));
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

// ---------- drawer ----------
function openDrawer(attraction, pass) {
  const lib = STATE.libs.find(l => l.id === pass.library_id);
  const branches = (pass.pickup_branches || []).map(bid => STATE.branches[bid]).filter(Boolean);
  const dist = STATE.homeGeo && attraction.geo ? haversineMi(STATE.homeGeo, attraction.geo) : null;

  const audRows = (pass.coupon?.audience_policies || []).map(p => {
    const label = fmtAudienceLabel(p) || p.audience || "—";
    const val = fmtAmount(p);
    const cnt = p.count ? `, ×${p.count}` : "";
    return `<tr><td>${label}</td><td>${val}${cnt}</td></tr>`;
  }).join("") || "<tr><td colspan=2>(no policy)</td></tr>";

  const cap = formatCapacity(pass.coupon?.capacity) || "—";

  const restEntries = Object.entries(pass.restrictions || {}).filter(([_, v]) =>
    v != null && v !== false && (!Array.isArray(v) || v.length > 0));
  const restRows = restEntries.length
    ? restEntries.map(([k, v]) => `<tr><td>${k}</td><td>${Array.isArray(v) ? v.join(", ") : v}</td></tr>`).join("")
    : "";

  const branchHtml = branches.length
    ? branches.map(br => `<tr><td>Branch</td><td>${br.name}${br.address?.street ? "<br><span style='font-size:11px;color:var(--ink-3)'>" + br.address.street + "</span>" : ""}</td></tr>`).join("")
    : "";

  $("#drawer-title").textContent = `${attraction.museum_name} × ${lib?.name || pass.library_id}`;
  $("#drawer-body").innerHTML = `
    <h4>Coupon</h4>
    <table><tbody>${audRows}</tbody></table>
    <div style="margin-top:6px;font-size:11px;color:var(--ink-3)">Capacity: ${cap}</div>

    <h4>Acquisition</h4>
    <table><tbody>
      <tr><td>Pass type</td><td>${PASS_TYPE_META[pass.pass_type]?.label || pass.pass_type} <span style="color:var(--ink-3)">(${pass.pass_type})</span></td></tr>
      <tr><td>Pickup</td><td>${pass.pickup_method}</td></tr>
      <tr><td>Raw label</td><td><code>${pass.pass_type_raw || "—"}</code></td></tr>
      ${branchHtml}
    </tbody></table>

    ${restRows ? `<h4>Restrictions</h4>
      <div class="restrictions"><table><tbody>${restRows}</tbody></table></div>` : ""}

    <h4>Attraction</h4>
    <table><tbody>
      <tr><td>Adult price</td><td>${attraction.original_price?.age_pricing?.adult?.price ? "$" + attraction.original_price.age_pricing.adult.price : "—"}</td></tr>
      <tr><td>Address</td><td>${attraction.address || "—"}</td></tr>
      ${dist != null ? `<tr><td>Distance</td><td>${dist.toFixed(1)} mi from ${STATE.homeGeo.zip}</td></tr>` : ""}
      <tr><td>Website</td><td><a href="${attraction.website}" target="_blank" rel="noopener" style="color:var(--g)">${attraction.website || "—"}</a></td></tr>
    </tbody></table>

    <a class="src-link" href="${pass.source_url}" target="_blank" rel="noopener">Source: ${pass.source_url}</a>
  `;
  $("#drawer").classList.add("open");
}
$("#drawer-close").addEventListener("click", () => $("#drawer").classList.remove("open"));

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

// ---------- booking modal ----------
function openBookModal(attraction, pass) {
  const lib = STATE.libs.find(l => l.id === pass.library_id);
  const libName = lib?.name || pass.library_id;
  const barcode = STATE.cards[pass.library_id] || "";
  $("#book-title").textContent = `Book pass — ${attraction.museum_name}`;
  const credBlock = barcode
    ? `<div class="cred-label">Card number to use</div>
       <div class="cred-box">${barcode}</div>
       <p style="margin-top:8px;font-size:11px;color:var(--ink-3)">Pass type: ${PASS_TYPE_META[pass.pass_type]?.label || pass.pass_type}</p>`
    : `<div class="cred-missing"><b>No card number stored for ${libName}.</b><br>Open the card-manager (sidebar) and add a barcode for <code>${pass.library_id}</code> to enable copy.</div>`;
  const primaryLabel = barcode
    ? "Copy card # and go →"
    : "Open booking page →";
  $("#book-body").innerHTML = `
    <div class="cred-label">Library card required</div>
    <div class="cred-box">${libName}</div>
    <div style="margin-top:14px">${credBlock}</div>
    <p style="margin-top:14px;font-size:11px;color:var(--ink-3);word-break:break-all">
      Will open: <a href="${pass.source_url}" target="_blank" rel="noopener" style="color:var(--g)">${pass.source_url}</a>
    </p>
    <div class="modal-row">
      <button class="modal-btn" id="book-cancel">Cancel</button>
      <button class="modal-btn primary" id="book-go">${primaryLabel}<span class="copied-toast" id="copied-toast">copied ✓</span></button>
    </div>
  `;
  $("#book-modal").classList.add("open");
  $("#book-backdrop").classList.add("open");
  $("#book-cancel").addEventListener("click", closeBookModal);
  $("#book-go").addEventListener("click", async () => {
    if (barcode) {
      try { await navigator.clipboard.writeText(barcode); $("#copied-toast").classList.add("show"); }
      catch (e) { console.warn("clipboard:", e); }
    }
    setTimeout(() => {
      window.open(pass.source_url, "_blank", "noopener,noreferrer");
      closeBookModal();
    }, barcode ? 280 : 0);
  });
}
function closeBookModal() {
  $("#book-modal").classList.remove("open");
  $("#book-backdrop").classList.remove("open");
}
$("#book-close").addEventListener("click", closeBookModal);
$("#book-backdrop").addEventListener("click", closeBookModal);

// ---------- cards manager ----------
function openCardsModal() {
  $("#cards-json").value = JSON.stringify(STATE.cards, null, 2);
  $("#cards-status").textContent = "";
  $("#cards-status").className = "hint";
  $("#cards-modal").classList.add("open");
  $("#cards-backdrop").classList.add("open");
}
function closeCardsModal() {
  $("#cards-modal").classList.remove("open");
  $("#cards-backdrop").classList.remove("open");
}
$("#cards-close").addEventListener("click", closeCardsModal);
$("#cards-cancel").addEventListener("click", closeCardsModal);
$("#cards-backdrop").addEventListener("click", closeCardsModal);
$("#cards-save").addEventListener("click", () => {
  const txt = $("#cards-json").value.trim();
  let obj;
  try { obj = txt ? JSON.parse(txt) : {}; }
  catch (e) {
    $("#cards-status").textContent = `Invalid JSON: ${e.message}`;
    $("#cards-status").className = "hint warn"; return;
  }
  if (typeof obj !== "object" || Array.isArray(obj)) {
    $("#cards-status").textContent = "Must be a JSON object."; $("#cards-status").className = "hint warn"; return;
  }
  saveCards(obj);
  $("#cards-status").textContent = `Saved ${Object.keys(obj).length} card(s).`;
  $("#cards-status").className = "hint ok";
  updateCardsHint();
});

function updateCardsHint() {
  const n = Object.keys(STATE.cards).length;
  $("#cards-hint").textContent = n
    ? `${n} card number(s) stored locally. Used by Book → button.`
    : "No cards stored. Add some via Manage… to enable copy-on-Book.";
}

// ---------- wire-up ----------
async function init() {
  loadCards();
  await loadData();
  updateCardsHint();
  renderLibList();
  updateLibCount();
  renderCategoryFilter();
  renderMatrix();

  $("#lib-filter").addEventListener("input", renderLibList);
  $("#btn-all").addEventListener("click", () => {
    STATE.selectedLibs = new Set(STATE.libs.map(l => l.id));
    renderLibList(); updateLibCount(); renderMatrix();
  });
  $("#btn-none").addEventListener("click", () => {
    STATE.selectedLibs.clear();
    renderLibList(); updateLibCount(); renderMatrix();
  });
  $("#btn-manage-cards").addEventListener("click", openCardsModal);
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
