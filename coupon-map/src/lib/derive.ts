// Pure presentation derivations. Throws on unknown enums (validate.ts catches
// this at load — by the time the UI calls these, inputs are already trusted).
// IMPORTANT: NEVER recompute discount amounts. coupon.summary is the only
// truth shown to the user.
import type {
  Eligibility,
  Library,
  Pass,
  PassForm,
  Residency,
  Verdict,
} from "../data/types";

// ── pass_form → 领取方式 (confirmed mapping) ─────────────────────────────
export interface FormLabel {
  icon: string;        // ✉ / ☆ / ☆☆
  short: string;       // Email / Pickup / Pickup&return
  tooltip: string;     // long Chinese
}
export function formLabel(f: PassForm): FormLabel {
  switch (f) {
    case "digital_email":
      return { icon: "✉", short: "Email", tooltip: "邮件电子券:下单后自动发邮件" };
    case "physical_coupon":
      return { icon: "☆", short: "Pickup", tooltip: "去图书馆领纸质优惠券,领走即可" };
    case "physical_circ":
      return { icon: "☆☆", short: "Pickup & return", tooltip: "借实体通行证,用完需归还" };
  }
}

// ── booking_access_probe.verdict (per-pass card scope) ───────────────────
export function verdictLabel(v: Verdict | undefined) {
  switch (v) {
    case "network_open":
      return { dot: "🟢", text: "本 network 任意卡", tone: "g" as const };
    case "own_card_only":
      return { dot: "🔴", text: "仅本馆卡", tone: "rd" as const };
    case "ambiguous":
      return { dot: "🟠", text: "存疑", tone: "or" as const };
    case "not_verified":
    default:
      return { dot: "⚪", text: "未验证", tone: "ink-3" as const };
  }
}

// ── library.card_eligibility (residency to get the card) ─────────────────
export function eligibilityLabel(e: Eligibility) {
  switch (e) {
    case "ma_resident":
      return { text: "MA 居民", warn: false, tooltip: "MA 居民均可,等同无 residency 限制" };
    case "town_resident":
      return { text: "⚠ 仅本镇居民", warn: true, tooltip: "仅本镇居民可办卡" };
    case "town_or_works":
      return { text: "本镇居民或工作者", warn: true, tooltip: "本镇居民或在本镇工作" };
    case "network":
      return { text: "本 network 居民", warn: false, tooltip: "本 network 覆盖范围内居民" };
    case "unknown":
      return { text: "未知", warn: false, tooltip: "未确认" };
  }
}

// ── pass-level residency (pickup residency, per [[product_dimension_pass_pickup_residency]]) ─
export function passResidencyLabel(r: Residency | undefined) {
  switch (r) {
    case "yes":
      return { text: "⚠ 取券有 residency 限制", warn: true };
    case "no":
      return { text: "取券无 residency 限制", warn: false };
    case "unknown":
    default:
      return { text: "取券限制未知", warn: false };
  }
}

// ── monthly booking-frequency limit (mostly free text, rarely set) ───────
export function frequencyLimit(s: string | null | undefined): string | null {
  if (!s) return null;
  return s; // raw verbatim — never inject our own number
}

// ── availability summary for a cell: any future date 'available'? ────────
export type AvailKind = "has_avail" | "all_booked" | "all_closed" | "none";
export function availabilitySummary(avail: Record<string, string> | undefined, today = new Date()): AvailKind {
  if (!avail) return "none";
  const todayStr = today.toISOString().slice(0, 10);
  let hasAvail = false;
  let hasBooked = false;
  let hasFuture = false;
  for (const [d, st] of Object.entries(avail)) {
    if (d < todayStr) continue;
    hasFuture = true;
    if (st === "available") hasAvail = true;
    else if (st === "booked") hasBooked = true;
  }
  if (!hasFuture) return "none";
  if (hasAvail) return "has_avail";
  if (hasBooked) return "all_booked";
  return "all_closed";
}

// ── card-matching: given the user's stored cards + a target pass, is there
// any card the user can use to pick up this pass? ────────────────────────
export interface StoredCard {
  id: string;
  library_id: string;
  card_number: string;
  note?: string;
}
export function matchCards(
  cards: StoredCard[],
  pass: Pass,
  libById: Map<string, Library>
): { exact: StoredCard[]; network: StoredCard[] } {
  const targetLib = libById.get(pass.library_id);
  if (!targetLib) return { exact: [], network: [] };
  const verdict = pass.booking_access_probe?.verdict;
  const exact = cards.filter((c) => c.library_id === pass.library_id);
  if (verdict === "own_card_only") return { exact, network: [] };
  // network_open / not_verified / ambiguous → any same-network card works as a candidate
  const network = cards.filter((c) => {
    if (c.library_id === pass.library_id) return false;
    const cl = libById.get(c.library_id);
    return cl?.network === targetLib.network;
  });
  return { exact, network };
}

// ── attraction adult price (display only) ────────────────────────────────
export function adultPrice(a: { prices?: Array<{ audience: string; price: number | null }> }): number | null {
  const p = a.prices?.find((x) => x.audience === "adult");
  return p?.price ?? null;
}

// ── reservation flag ─────────────────────────────────────────────────────
export function reservationFlag(a: { reservation?: { required?: string } }) {
  const r = a.reservation?.required;
  if (!r || r === "walk_in_ok") return { need: false, text: "可直接到访", tone: "g" as const };
  return { need: true, text: `需预约 (${r})`, tone: "or" as const };
}
