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
// `cellIcon` shows in the compact matrix cell — Email leaves it blank so the
// cell stays clean (Email is the implicit default). Solid stars distinguish
// pickup (★) from pickup-and-return (★★) at a glance.
export interface FormLabel {
  cellIcon: string;    // "" / ★ / ★★  (for cell glyph)
  icon: string;        // ✉ / ★ / ★★   (for popover row)
  short: string;       // Email / Pickup / Pickup&return
  tooltip: string;
}
export function formLabel(f: PassForm): FormLabel {
  switch (f) {
    case "digital_email":
      return { cellIcon: "", icon: "✉", short: "Email", tooltip: "邮件电子券:下单后自动发邮件" };
    case "physical_coupon":
      return { cellIcon: "★", icon: "★", short: "Pickup", tooltip: "去图书馆领纸质优惠券,领走即可" };
    case "physical_circ":
      return { cellIcon: "★★", icon: "★★", short: "Pickup & return", tooltip: "借实体通行证,用完需归还" };
  }
}

// ── booking_access_probe.verdict (per-pass card scope) ───────────────────
// Returns a label spelled out with the lib's actual network/town so the user
// doesn't have to remember what each verdict means. All 4 possible categories:
//   network_open  — 同 network 任意卡都能用
//   own_card_only — 只接受本馆发的卡(连同 network 其他馆的卡也不行)
//   not_verified  — 从未做 booking probe
//   ambiguous     — 跑过 probe 但无可订日期可测/结果不确定
export function verdictLabel(
  v: Verdict | undefined,
  ctx?: { network?: string; town?: string }
) {
  const net = ctx?.network ?? "Network";
  const town = ctx?.town ?? "Own";
  switch (v) {
    case "network_open":
      return { dot: "🟢", text: `Any ${net} card`, tone: "g" as const };
    case "own_card_only":
      return { dot: "🔴", text: `${town} card only`, tone: "rd" as const };
    case "ambiguous":
      return { dot: "🟠", text: "Ambiguous", tone: "or" as const };
    case "not_verified":
    default:
      return { dot: "⚪", text: "Not verified", tone: "ink-3" as const };
  }
}

// All 4 possible verdict categories — used by the matrix legend.
export const VERDICT_CATEGORIES: Verdict[] = [
  "network_open",
  "own_card_only",
  "ambiguous",
  "not_verified",
];

// ── library.card_eligibility (residency to get the card) ─────────────────
// All 5 possible categories:
//   ma_resident   — 任何 MA 居民
//   town_resident — 仅本镇居民
//   town_or_works — 本镇居民 OR 在本镇工作 / 上学 / 持物业
//   network       — 本 network 覆盖区居民
//   unknown       — 未确认
export function eligibilityLabel(
  e: Eligibility,
  ctx?: { network?: string; town?: string }
) {
  const net = ctx?.network ?? "Network";
  const town = ctx?.town ?? "Town";
  switch (e) {
    case "ma_resident":
      return { text: "MA Resident", warn: false, tooltip: "Any MA resident may apply" };
    case "town_resident":
      return { text: `${town} Resident only`, warn: true, tooltip: `${town} residents only` };
    case "town_or_works":
      return { text: `${town} Resident or Worker`, warn: true, tooltip: `Residents, workers, students, property owners of ${town}` };
    case "network":
      return { text: `${net} Network`, warn: false, tooltip: `Residents within the ${net} service area` };
    case "unknown":
      return { text: "Unknown", warn: false, tooltip: "Eligibility not confirmed" };
  }
}

export const ELIGIBILITY_CATEGORIES: Eligibility[] = [
  "ma_resident",
  "town_resident",
  "town_or_works",
  "network",
  "unknown",
];

// ── pass-level residency (pickup residency) ──────────────────────────────
// All 3 categories. yes=取这张 pass 时被验居住地;scope 通常是 town,即
// 必须是该馆所在 town 的居民才能取这张 pass。
export function passResidencyLabel(
  r: Residency | undefined,
  scope?: string | null,
  ctx?: { town?: string }
) {
  const town = ctx?.town ?? "Town";
  switch (r) {
    case "yes":
      if (scope === "town") return { text: `${town} Residents only`, warn: true };
      if (scope === "ma") return { text: "MA Residents only", warn: true };
      return { text: "Residency restricted", warn: true };
    case "no":
      return { text: "No restriction", warn: false };
    case "unknown":
    default:
      return { text: "Unknown", warn: false };
  }
}

export const RESIDENCY_CATEGORIES: Residency[] = ["no", "yes", "unknown"];

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

// ── audience policy formatting (used in cell detail) ─────────────────────
const AUDIENCE_LABEL: Record<string, string> = {
  adult: "成人",
  child: "儿童",
  children: "儿童",
  senior: "老人",
  youth: "青少年",
  student: "学生",
  military: "军人",
  veteran: "退伍军人",
  educator: "教师",
  teacher: "教师",
  family: "家庭",
  everyone: "所有人",
  infant: "婴幼儿",
  toddler: "幼儿",
  preschool: "学龄前",
  resident: "本地居民",
  member: "会员",
  group: "团体",
};
export function audienceLabel(a: string): string {
  return AUDIENCE_LABEL[a.toLowerCase()] || a;
}

export interface AudiencePolicy {
  audience: string;
  age_range?: { min: number | null; max: number | null } | null;
  count?: number | null;
  form?: string;
  value?: number | null;
}
export function policyText(p: AudiencePolicy): string {
  const v = p.value;
  switch ((p.form || "").toLowerCase()) {
    case "percent-off":
      return v != null ? `-${v}%` : "% off";
    case "free":
      return "FREE";
    case "dollars-off":
    case "dollar-off":
      return v != null ? `-$${v}` : "$ off";
    case "fixed-price":
      return v != null ? `$${v}/人` : "固定价";
    case "fixed-total":
      return v != null ? `共 $${v}` : "固定总价";
    case "bogo":
      return "B1G1";
    default:
      return [p.form, v].filter((x) => x !== undefined && x !== null && x !== "").join(" ").trim() || "—";
  }
}

// Compact discount for the matrix cell — picks the primary audience policy
// and returns a short label like "-50%", "$10", "-$2", "FREE", "B1G1", "$8.5".
// If we fall back to coupon.summary, strip per-person suffixes ("/person",
// "/p", "/人", "/each") so the cell stays compact, and shorten a bare
// "discount" (no number) to "DISC".
const stripPerUnit = (s: string) =>
  s.replace(/\s*\/\s*(?:person|each\s+person|each|p|人)\b/i, "").trim();
const abbreviateBareWord = (s: string) =>
  /^discount$/i.test(s.trim()) ? "DISC" : s;
export function simpleDiscount(coupon: {
  summary?: string;
  audience_policies?: AudiencePolicy[];
} | null | undefined): string {
  if (!coupon) return "—";
  const policies = coupon.audience_policies || [];
  if (policies.length === 0) return abbreviateBareWord(stripPerUnit(coupon.summary || "—"));
  // Prefer an "Everyone" / "Adult" policy; otherwise first.
  const primary =
    policies.find((p) => /everyone/i.test(p.audience)) ||
    policies.find((p) => /adult/i.test(p.audience)) ||
    policies[0];
  const v = primary.value;
  switch ((primary.form || "").toLowerCase()) {
    case "percent-off":
      return v != null ? `-${v}%` : abbreviateBareWord(stripPerUnit(coupon.summary || "—"));
    case "free":
      return "FREE";
    case "dollars-off":
    case "dollar-off":
      return v != null ? `-$${v}` : abbreviateBareWord(stripPerUnit(coupon.summary || "—"));
    case "fixed-price":
      return v != null ? `$${v}` : abbreviateBareWord(stripPerUnit(coupon.summary || "—"));
    case "fixed-total":
      return v != null ? `$${v}` : abbreviateBareWord(stripPerUnit(coupon.summary || "—"));
    case "bogo":
      return "B1G1";
    default:
      return abbreviateBareWord(stripPerUnit(coupon.summary || "—"));
  }
}

// Structured capacity: total people + per-audience breakdown when present.
// Returns { total, parts? } where parts is e.g. ["1 大", "1 小"] or undefined
// when only a total is known.
export function capacityStructure(coupon: {
  capacity?: { kind?: string; n?: number | null };
  audience_policies?: AudiencePolicy[];
} | null | undefined): { total: number | null; parts?: string[] } {
  const total = coupon?.capacity?.n ?? null;
  const policies = coupon?.audience_policies || [];
  const withCount = policies.filter((p) => p.count != null && p.count > 0);
  if (withCount.length === 0) return { total };
  const audMap: Record<string, string> = {
    adult: "大",
    senior: "老",
    child: "小",
    children: "小",
    youth: "青",
    student: "学",
    infant: "婴",
    everyone: "人",
    family: "家",
    military: "军",
  };
  const parts = withCount.map((p) => {
    const aud = (p.audience || "").toLowerCase();
    const tag = audMap[aud] || p.audience;
    return `${p.count} ${tag}`;
  });
  return { total, parts };
}
export function policyRange(p: AudiencePolicy): string {
  if (!p.age_range || (p.age_range.min == null && p.age_range.max == null)) return "";
  const { min, max } = p.age_range;
  if (min != null && max != null) return ` (${min}-${max} 岁)`;
  if (min != null) return ` (${min}+ 岁)`;
  if (max != null) return ` (≤${max} 岁)`;
  return "";
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
