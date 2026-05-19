// MuseumPapa Admin Panel — interactive matrix viewer for libraries × attractions
// Data source: ../data/structured/{passes,libraries,attractions,branches}.json

const OWNED_LIB_IDS = new Set(["wakefield", "reading", "bpl", "wilmington", "somerville"]);

const STATE = {
  libs: [],
  attractions: [],
  branches: {},      // id -> branch
  passes: [],
  passesByAttr: {},  // slug -> [pass...]
  selectedLibs: new Set(),
  audience: { adult: 2, child: 2, senior: 0, youth: 0 },
  homeGeo: null,     // {lat, lng, zip}
  showOnlyCovered: true,
  showRestrictions: true,
  sortMode: "coverage-desc",
  categoryFilter: "",
};

// ---------- helpers ----------
function $(sel) { return document.querySelector(sel); }
function $$(sel) { return [...document.querySelectorAll(sel)]; }
function el(tag, attrs = {}, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") e.className = v;
    else if (k === "html") e.innerHTML = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v);
  }
  for (const kid of kids.flat()) {
    if (kid == null) continue;
    e.appendChild(typeof kid === "string" ? document.createTextNode(kid) : kid);
  }
  return e;
}

function haversineMi(a, b) {
  if (!a || !b) return null;
  const R = 3958.8, toRad = (x) => x * Math.PI / 180;
  const dLat = toRad(b.lat - a.lat), dLng = toRad(b.lng - a.lng);
  const s = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(a.lat)) * Math.cos(toRad(b.lat)) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(s));
}

// ---------- data load ----------
async function loadData() {
  const fetchJson = (p) => fetch(p).then((r) => {
    if (!r.ok) throw new Error(`${p} ${r.status}`); return r.json();
  });
  const [libsD, attrsD, branchesD, passesD] = await Promise.all([
    fetchJson("../data/structured/libraries.json"),
    fetchJson("../data/structured/attractions.json"),
    fetchJson("../data/structured/branches.json"),
    fetchJson("../data/structured/passes.json"),
  ]);
  STATE.libs = libsD.libraries.sort((a, b) => a.name.localeCompare(b.name));
  STATE.attractions = attrsD.attractions;
  for (const br of branchesD.branches) STATE.branches[br.id] = br;
  STATE.passes = passesD.passes;
  STATE.passesByAttr = {};
  for (const p of STATE.passes) {
    (STATE.passesByAttr[p.attraction_slug] ||= []).push(p);
  }
  // default selection: owned libs that exist
  STATE.selectedLibs = new Set(STATE.libs.filter(l => OWNED_LIB_IDS.has(l.id)).map(l => l.id));
}

// ---------- coupon strength & label ----------
// Returns a numeric score (higher = better) for ranking BEST cell
function couponStrength(pass, attraction) {
  if (!pass) return -1;
  const c = pass.coupon || {};
  const pols = c.audience_policies || [];
  let s = 0;
  for (const pol of pols) {
    if (pol.form === "free") s = Math.max(s, 1000);
    else if (pol.form === "percent-off") s = Math.max(s, pol.value || 0);
    else if (pol.form === "dollar-off") s = Math.max(s, (pol.value || 0) * 2);
    else if (pol.form === "per-person-price") {
      // lower price = stronger; compare against attraction.original_price.age_pricing.adult
      const orig = attraction?.original_price?.age_pricing?.adult?.price;
      if (orig && pol.value < orig) s = Math.max(s, ((orig - pol.value) / orig) * 100);
    } else if (pol.form === "discount") s = Math.max(s, pol.value || 0);
  }
  return s;
}

function classifyCouponClass(pass) {
  const pols = pass?.coupon?.audience_policies || [];
  if (pols.some(p => p.form === "free")) return "free";
  const forms = new Set(pols.map(p => p.form));
  if (forms.has("percent-off")) return "pct";
  if (forms.has("dollar-off"))  return "dollar";
  if (forms.has("per-person-price")) return "perp";
  if (forms.has("discount")) return "disc";
  return "";
}

function summaryLabel(pass) {
  const pols = pass?.coupon?.audience_policies || [];
  if (!pols.length) return "—";
  // most discounted policy wins for label
  const labels = pols.map(p => {
    const a = p.audience && p.audience !== "Everyone" ? p.audience[0] : "";
    if (p.form === "free") return a ? `${a}:FREE` : "FREE";
    if (p.form === "percent-off") return `${p.value}% off${a ? " " + a : ""}`;
    if (p.form === "dollar-off") return `$${p.value} off${a ? " " + a : ""}`;
    if (p.form === "per-person-price") return `$${p.value}${a ? "/" + a.toLowerCase() : "/pp"}`;
    if (p.form === "discount") return `disc:${p.value}`;
    return p.form;
  });
  return labels.join(" · ");
}

function methodIcon(pass) {
  const m = pass?.pickup_method;
  if (m === "digital") return "📧";
  if (m === "physical_at_branch") return "🏛";
  return "·";
}

function audienceIcons(pass) {
  const pols = pass?.coupon?.audience_policies || [];
  const set = new Set();
  for (const p of pols) {
    if (p.audience === "Everyone") set.add("👨").add("👧").add("👴");
    else if (p.audience === "Adult") set.add("👨");
    else if (p.audience === "Child") set.add("👧");
    else if (p.audience === "Senior") set.add("👴");
    else if (p.audience === "Youth") set.add("🧑");
    else if (p.audience === "Vehicle") set.add("🚗");
  }
  return [...set].join("");
}

// ---------- BEST computation per attraction ----------
function bestPassFor(attraction) {
  const slug = attraction.slug;
  const candidates = (STATE.passesByAttr[slug] || []).filter(p => STATE.selectedLibs.has(p.library_id));
  if (!candidates.length) return null;
  let best = candidates[0], bestScore = couponStrength(best, attraction);
  for (const p of candidates.slice(1)) {
    const s = couponStrength(p, attraction);
    if (s > bestScore) { best = p; bestScore = s; }
  }
  return best;
}

// ---------- rendering ----------
function renderLibList() {
  const wrap = $("#lib-list");
  const q = ($("#lib-filter").value || "").toLowerCase();
  wrap.innerHTML = "";
  for (const l of STATE.libs) {
    if (q && !l.name.toLowerCase().includes(q) && !l.id.includes(q)) continue;
    const owned = OWNED_LIB_IDS.has(l.id);
    const lab = el("label", { class: owned ? "owned" : "" },
      el("input", {
        type: "checkbox",
        ...(STATE.selectedLibs.has(l.id) ? { checked: "checked" } : {}),
        onchange: (e) => {
          if (e.target.checked) STATE.selectedLibs.add(l.id);
          else STATE.selectedLibs.delete(l.id);
          renderMatrix(); updateLibCount();
        },
      }),
      `${l.name}`
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

function sortedAttractions() {
  const list = [...STATE.attractions];
  if (STATE.categoryFilter) {
    return list.filter(a => (a.categories || []).includes(STATE.categoryFilter)).sort(sortCmp);
  }
  return list.sort(sortCmp);
  function sortCmp(a, b) {
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
    return 0;
  }
}

function renderMatrix() {
  const tbody = $("#matrix-body");
  const thead = $("#matrix-head");
  thead.innerHTML = ""; tbody.innerHTML = "";

  const selLibs = STATE.libs.filter(l => STATE.selectedLibs.has(l.id));

  // headers
  thead.appendChild(el("th", { class: "attr-col" }, "Attraction"));
  thead.appendChild(el("th", { class: "best-col" }, "👑 BEST"));
  for (const l of selLibs) thead.appendChild(el("th", {}, l.name.replace(" Public Library", "").replace(" Library", "")));

  // body
  const attrs = sortedAttractions();
  const visibleAttrs = [];
  for (const a of attrs) {
    const best = bestPassFor(a);
    if (STATE.showOnlyCovered && !best) continue;
    visibleAttrs.push({ a, best });
  }

  // top-3 nearest BEST(by distance from home)
  let nearestSlugs = new Set();
  if (STATE.homeGeo) {
    const distList = visibleAttrs
      .filter(v => v.best && v.a.geo?.lat)
      .map(v => ({ slug: v.a.slug, d: haversineMi(STATE.homeGeo, v.a.geo) }))
      .filter(x => x.d != null)
      .sort((x, y) => x.d - y.d)
      .slice(0, 3);
    nearestSlugs = new Set(distList.map(x => x.slug));
  }

  for (const { a, best } of visibleAttrs) {
    const tr = el("tr");
    const origPrice = a.original_price?.age_pricing?.adult?.price;
    const dist = STATE.homeGeo && a.geo ? haversineMi(STATE.homeGeo, a.geo) : null;
    tr.appendChild(el("td", { class: "attr-col" },
      el("span", { class: "attr-name" }, a.museum_name),
      el("span", { class: "attr-meta" },
        `${origPrice ? "$" + origPrice + " adult" : "no price"}${dist != null ? " · " + dist.toFixed(1) + "mi" : ""}`)
    ));

    // BEST cell
    if (best) {
      const klass = `cell best ${nearestSlugs.has(a.slug) ? "nearest" : ""}`;
      const lib = STATE.libs.find(l => l.id === best.library_id);
      const distLabel = dist != null ? `${dist.toFixed(1)}mi` : "";
      tr.appendChild(el("td", {},
        el("div", { class: klass, onclick: () => openDrawer(a, best) },
          el("div", { class: "cell-summary" }, `${nearestSlugs.has(a.slug) ? "🏠 " : ""}${summaryLabel(best)}`),
          el("div", { class: "cell-icons" }, `${methodIcon(best)} ${audienceIcons(best)} · ${lib?.name.replace(" Public Library", "").replace(" Library", "") || best.library_id}${best.restrictions && STATE.showRestrictions ? " ⚠" : ""}`),
          distLabel ? el("div", { class: "dist" }, distLabel) : null,
        )));
    } else {
      tr.appendChild(el("td", {}, el("div", { class: "cell cell-empty" }, "—")));
    }

    // per-lib cells
    for (const l of selLibs) {
      const pass = (STATE.passesByAttr[a.slug] || []).find(p => p.library_id === l.id);
      if (!pass) { tr.appendChild(el("td", {}, el("div", { class: "cell cell-empty" }, "—"))); continue; }
      const cls = `cell ${classifyCouponClass(pass)}`;
      tr.appendChild(el("td", {},
        el("div", { class: cls, onclick: () => openDrawer(a, pass) },
          el("div", { class: "cell-summary" }, summaryLabel(pass)),
          el("div", { class: "cell-icons" }, `${methodIcon(pass)} ${audienceIcons(pass)}${pass.restrictions && STATE.showRestrictions ? " ⚠" : ""}`),
        )));
    }
    tbody.appendChild(tr);
  }

  // summary stat
  const totalCovered = visibleAttrs.filter(v => v.best).length;
  const freeCount = visibleAttrs.filter(v => v.best && classifyCouponClass(v.best) === "free").length;
  $("#stat-summary").textContent = `${STATE.selectedLibs.size} libs selected · ${totalCovered}/${STATE.attractions.length} attractions covered · ${freeCount} FREE${STATE.homeGeo ? " · home " + STATE.homeGeo.zip : ""}`;
}

// ---------- drawer ----------
function openDrawer(attraction, pass) {
  const lib = STATE.libs.find(l => l.id === pass.library_id);
  const branches = (pass.pickup_branches || []).map(bid => STATE.branches[bid]).filter(Boolean);
  const dist = STATE.homeGeo && attraction.geo ? haversineMi(STATE.homeGeo, attraction.geo) : null;

  const audRows = (pass.coupon?.audience_policies || []).map(p => {
    const valLabel = p.form === "free" ? "FREE"
      : p.form === "percent-off" ? `${p.value}% off`
      : p.form === "dollar-off" ? `$${p.value} off`
      : p.form === "per-person-price" ? `$${p.value} per person`
      : p.form === "discount" ? `discount ${p.value}` : p.form;
    const ageLabel = p.age_range ? ` (${p.age_range.min ?? ""}-${p.age_range.max ?? ""})` : "";
    return `<tr><td>${p.audience}${ageLabel}</td><td>${valLabel}${p.count ? " · count " + p.count : ""}</td></tr>`;
  }).join("");
  const cap = pass.coupon?.capacity;
  const capLabel = cap ? `${cap.n} ${cap.kind}` : "—";

  const restRows = pass.restrictions ? Object.entries(pass.restrictions)
    .filter(([k, v]) => v != null && v !== false && (!Array.isArray(v) || v.length))
    .map(([k, v]) => `<tr><td>${k}</td><td>${Array.isArray(v) ? v.join(", ") : v}</td></tr>`).join("") : "";

  $("#drawer-title").textContent = `${attraction.museum_name} × ${lib?.name || pass.library_id}`;
  $("#drawer-body").innerHTML = `
    <h4>Coupon · 优惠</h4>
    <table><tbody>${audRows || "<tr><td colspan=2>(no policy)</td></tr>"}</tbody></table>
    <div style="margin-top:6px;font-size:11px;color:#6e6e73">Capacity: ${capLabel}</div>

    <h4>Acquisition · 获取方式</h4>
    <table><tbody>
      <tr><td>Method</td><td>${pass.pass_type_raw || pass.pass_type}</td></tr>
      <tr><td>Pickup</td><td>${pass.pickup_method}</td></tr>
      ${branches.length ? branches.map(br => `<tr><td>Branch</td><td>${br.name}<br><span style="font-size:11px;color:#6e6e73">${br.address || ""}</span></td></tr>`).join("") : ""}
    </tbody></table>

    ${restRows ? `<h4>Restrictions · 限制</h4>
      <div class="restrictions"><table><tbody>${restRows}</tbody></table></div>` : ""}

    <h4>Attraction · 景点</h4>
    <table><tbody>
      <tr><td>Adult price</td><td>${attraction.original_price?.age_pricing?.adult?.price ? "$" + attraction.original_price.age_pricing.adult.price : "—"}</td></tr>
      <tr><td>Address</td><td>${attraction.address || "—"}</td></tr>
      ${dist != null ? `<tr><td>Distance</td><td>${dist.toFixed(1)} mi from ${STATE.homeGeo.zip}</td></tr>` : ""}
      <tr><td>Website</td><td><a href="${attraction.website}" target="_blank" rel="noopener">${attraction.website || "—"}</a></td></tr>
    </tbody></table>

    <a class="src-link" href="${pass.source_url}" target="_blank" rel="noopener">Source: ${pass.source_url}</a>
  `;
  $("#drawer").classList.add("open");
}
$("#drawer-close").addEventListener("click", () => $("#drawer").classList.remove("open"));

// ---------- ZIP geocoding via zippopotam.us ----------
async function geocodeZip(zip) {
  const cacheKey = `zipgeo:${zip}`;
  const cached = localStorage.getItem(cacheKey);
  if (cached) return JSON.parse(cached);
  const r = await fetch(`https://api.zippopotam.us/us/${zip}`);
  if (!r.ok) throw new Error(`zippopotam ${r.status}`);
  const data = await r.json();
  const place = data.places?.[0];
  if (!place) throw new Error("no place");
  const geo = { lat: parseFloat(place.latitude), lng: parseFloat(place.longitude), zip, name: place["place name"] };
  localStorage.setItem(cacheKey, JSON.stringify(geo));
  return geo;
}

// ---------- wire up controls ----------
async function init() {
  await loadData();
  renderLibList();
  updateLibCount();
  renderCategoryFilter();
  renderMatrix();

  $("#lib-filter").addEventListener("input", renderLibList);
  $("#btn-owned").addEventListener("click", () => {
    STATE.selectedLibs = new Set(STATE.libs.filter(l => OWNED_LIB_IDS.has(l.id)).map(l => l.id));
    renderLibList(); updateLibCount(); renderMatrix();
  });
  $("#btn-all").addEventListener("click", () => {
    STATE.selectedLibs = new Set(STATE.libs.map(l => l.id));
    renderLibList(); updateLibCount(); renderMatrix();
  });
  $("#btn-none").addEventListener("click", () => {
    STATE.selectedLibs = new Set();
    renderLibList(); updateLibCount(); renderMatrix();
  });
  for (const id of ["aud-adult", "aud-child", "aud-senior", "aud-youth"]) {
    $("#" + id).addEventListener("change", (e) => {
      STATE.audience[id.replace("aud-", "")] = parseInt(e.target.value) || 0;
      renderMatrix();
    });
  }
  $("#opt-only-covered").addEventListener("change", (e) => { STATE.showOnlyCovered = e.target.checked; renderMatrix(); });
  $("#opt-show-restrictions").addEventListener("change", (e) => { STATE.showRestrictions = e.target.checked; renderMatrix(); });
  $("#opt-sort").addEventListener("change", (e) => { STATE.sortMode = e.target.value; renderMatrix(); });
  $("#opt-category").addEventListener("change", (e) => { STATE.categoryFilter = e.target.value; renderMatrix(); });

  $("#btn-geocode").addEventListener("click", async () => {
    const zip = ($("#home-zip").value || "").trim();
    const hint = $("#zip-hint");
    if (!/^\d{5}$/.test(zip)) {
      hint.textContent = "请输入 5 位 ZIP"; hint.className = "hint warn"; return;
    }
    hint.textContent = "解析中…"; hint.className = "hint";
    try {
      const geo = await geocodeZip(zip);
      STATE.homeGeo = geo;
      hint.textContent = `📍 ${geo.name}, lat ${geo.lat.toFixed(3)}, lng ${geo.lng.toFixed(3)}`;
      hint.className = "hint ok";
      renderMatrix();
    } catch (e) {
      hint.textContent = `解析失败: ${e.message}`; hint.className = "hint warn";
    }
  });
  $("#home-zip").addEventListener("keydown", (e) => { if (e.key === "Enter") $("#btn-geocode").click(); });
}

init().catch(e => { console.error(e); $("#stat-summary").textContent = "load error: " + e.message; });
