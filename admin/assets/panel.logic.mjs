// Pure, dependency-injected logic for the admin matrix. No global STATE, no DOM.
// Mirrors the funnel layer semantics in panel.js / web/src/lib/engine.ts.

// MA occupies the 010xx–027xx ZIP range (028xx–029xx = RI, 030xx+ = NH/ME).
// `maZips` (the ~59 seed-town set) is intentionally ignored: keying off it
// wrongly blocked genuine MA residents in other towns (e.g. 01886 Westford).
export function isMaZip(zip, _maZips) {
  if (!/^\d{5}$/.test(zip || "")) return false;
  const p = Number(String(zip).slice(0, 3));
  return p >= 10 && p <= 27;
}

// L1: do the held cards cover this library? (own id, OR a card in the same network)
// requiresOwnCard: this pass needs THIS library's own card — a same-network
// sibling card is rejected at booking, so the network fallback does NOT apply.
export function cardOk(lib, heldLibIds, libsById, requiresOwnCard = false) {
  if (heldLibIds.includes(lib.id)) return true;
  if (requiresOwnCard) return false;
  const nets = new Set(heldLibIds.map(id => libsById[id]?.network).filter(Boolean));
  return nets.has(lib.network);
}

// L3 (pass pickup residency) + L4 (attraction visitor residency) combined -> zip eligibility.
// "unknown" counts as ok-with-warn (never hide; flag for audit). Returns {ok, warn, reason}.
export function residencyOk(pass, lib, attr, homeZip, maZips) {
  let warn = false;
  const rr = pass?.residency_restriction;
  if (rr && rr.restricted === "yes") {
    if (rr.scope === "town") {
      if (!(lib.resident_zips || []).includes(homeZip))
        return { ok: false, reason: `${lib.town} residents only` };
    } else if (rr.scope === "ma") {
      if (!isMaZip(homeZip, maZips))
        return { ok: false, reason: "MA residents only" };
    } else {
      // Restricted, but scope is unknown/unevaluable — we can't clear it, so
      // never present it as a clean tier-A; flag for review. (Matches the
      // detail-popup path; was silently {ok:true,warn:false} here. A4.)
      warn = true;
    }
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
  if (adult) return adult;
  // No adult/Everyone policy: a bare "free" line is usually a secondary
  // child/infant benefit (e.g. "Single ticket 50% off" + "Child free").
  // Headline what a paying visitor gets unless every policy is free.
  // Mirrors build/coupons.py summary_for (P0-2).
  const nonFree = coupon.audience_policies.filter(p => p.form !== "free");
  return bestPolicy({ audience_policies: nonFree.length ? nonFree : coupon.audience_policies });
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
// Forms: FREE, -50%=percent-off, -$10=dollar-off, $9=per-person price,
// B1G1=bogo, disc=generic discount, ?=unknown / no coupon.
export function shortSummary(coupon) {
  const p = headlinePolicy(coupon);
  if (!p) return "?";
  switch (p.form) {
    case "free": return "FREE";
    case "percent-off": return p.value != null ? `-${p.value}%` : "%";
    case "dollar-off": return p.value != null ? `-$${p.value}` : "-$";
    case "per-person-price": return p.value != null ? `$${p.value}` : "$";
    case "bogo": return "B1G1";
    case "discount": return "disc";
    default: return "?";
  }
}
