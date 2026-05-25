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
      return { ok: false, reason: `${lib.town} residents only` };
    if (rr.scope === "ma" && !isMaZip(homeZip, maZips))
      return { ok: false, reason: "MA residents only" };
  } else if (rr && rr.restricted === "unknown") {
    warn = true;
  }
  const ve = attr?.visitor_eligibility;
  if (ve && ve.residency === "ma_resident" && !isMaZip(homeZip, maZips))
    return { ok: false, reason: "MA residents only (attraction)" };
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

// The "headline" policy a rep would quote: the adult/Everyone offer if present,
// else the strongest by discount type. Avoids quoting a "kids free" as the offer.
export function headlinePolicy(coupon) {
  if (!coupon || !coupon.audience_policies?.length) return null;
  const ADULT = new Set(["adult", "adults", "everyone", "all"]);
  const adult = coupon.audience_policies.find(
    p => ADULT.has(String(p.audience || "").toLowerCase()));
  return adult || bestPolicy(coupon);
}

// Long human summary (detail rows). Falls back to coupon.summary.
export function couponSummary(coupon) {
  if (!coupon) return "no offer info";
  if (coupon.summary) return coupon.summary;
  const p = headlinePolicy(coupon);
  if (!p) return "no offer info";
  switch (p.form) {
    case "free": return "FREE";
    case "percent-off": return `${p.value ?? ""}% off`;
    case "dollar-off": return `$${p.value ?? ""} off`;
    case "per-person-price": return `$${p.value ?? ""}/person`;
    case "bogo": return "BOGO";
    default: return "discount";
  }
}

// Ultra-short glyph for a matrix cell, based on the adult/headline policy.
// Forms: FR=free, 50%=percent-off, -$10=dollar-off, $X/p=per-person price,
// B1G1=bogo, disc=generic discount, ?=unknown / no coupon.
export function shortSummary(coupon) {
  const p = headlinePolicy(coupon);
  if (!p) return "?";
  switch (p.form) {
    case "free": return "FR";
    case "percent-off": return p.value != null ? `${p.value}%` : "%";
    case "dollar-off": return p.value != null ? `-$${p.value}` : "-$";
    case "per-person-price": return p.value != null ? `$${p.value}` : "$";
    case "bogo": return "B1G1";
    case "discount": return "disc";
    default: return "?";
  }
}
