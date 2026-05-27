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

function issuedCardGroups(lib) {
  const groups = Array.isArray(lib?.card_issuance_groups) && lib.card_issuance_groups.length
    ? lib.card_issuance_groups
    : [lib?.card_issuance_group || lib?.network].filter(Boolean);
  return new Set(groups);
}

function acceptedCardGroups(lib) {
  const groups = Array.isArray(lib?.card_auth_groups) && lib.card_auth_groups.length
    ? lib.card_auth_groups
    : [lib?.network].filter(Boolean);
  return new Set(groups);
}

function sharesAccessGroup(heldLib, targetLib) {
  const heldGroups = issuedCardGroups(heldLib);
  for (const group of acceptedCardGroups(targetLib)) {
    if (heldGroups.has(group)) return true;
  }
  return false;
}

export function bookingAccessMode(passOrRequiresOwnCard = false) {
  if (passOrRequiresOwnCard && typeof passOrRequiresOwnCard === "object") {
    const verdict = passOrRequiresOwnCard.booking_access_probe?.verdict;
    if (verdict === "own_card_only" || verdict === "network_open" || verdict === "ambiguous" || verdict === "not_verified") {
      return verdict;
    }
    return passOrRequiresOwnCard.requires_own_card ? "own_card_only" : "not_verified";
  }
  return passOrRequiresOwnCard ? "own_card_only" : "not_verified";
}

export function cardCoverage(lib, heldLibIds, libsById, passOrRequiresOwnCard = false) {
  if (heldLibIds.includes(lib.id)) return { ok: true, warn: false, mode: bookingAccessMode(passOrRequiresOwnCard) };
  const mode = bookingAccessMode(passOrRequiresOwnCard);
  if (mode === "own_card_only") return { ok: false, warn: false, mode };
  const ok = heldLibIds.some(id => sharesAccessGroup(libsById[id], lib));
  return { ok, warn: ok && (mode === "not_verified" || mode === "ambiguous"), mode };
}

// L1: do the held cards cover this library? (own id, OR a card in an accepted
// access group for this library).
// requiresOwnCard: this pass needs THIS library's own card — a sibling/access
// group fallback is rejected at booking, so the group fallback does NOT apply.
export function cardOk(lib, heldLibIds, libsById, passOrRequiresOwnCard = false) {
  return cardCoverage(lib, heldLibIds, libsById, passOrRequiresOwnCard).ok;
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

export function cellTier(cardOk_, zipOk_, warn = false) {
  if (cardOk_ && zipOk_ && warn) return "aw";
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

const TIER_RANK = { a: 0, aw: 1, b: 2, c: 3, d: 4 };
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
