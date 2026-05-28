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
  const net = ctx?.network ?? "network";
  const town = ctx?.town ?? "本馆";
  switch (v) {
    case "network_open":
      return { dot: "🟢", text: `${net} 网络任意卡可用`, tone: "g" as const };
    case "own_card_only":
      return { dot: "🔴", text: `仅 ${town} 本馆卡可用`, tone: "rd" as const };
    case "ambiguous":
      return { dot: "🟠", text: "已测,结果不确定 (无可订日期)", tone: "or" as const };
    case "not_verified":
    default:
      return { dot: "⚪", text: "尚未实测验证", tone: "ink-3" as const };
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
  const net = ctx?.network ?? "network";
  const town = ctx?.town ?? "本镇";
  switch (e) {
    case "ma_resident":
      return { text: "任何 MA 居民可办卡", warn: false, tooltip: "MA 居民均可,等同无 residency 限制" };
    case "town_resident":
      return { text: `⚠ 仅 ${town} 居民可办卡`, warn: true, tooltip: `仅 ${town} 居民可办卡` };
    case "town_or_works":
      return { text: `${town} 居民或工作者可办卡`, warn: true, tooltip: `${town} 居民,或在 ${town} 工作/上学/持物业者` };
    case "network":
      return { text: `${net} 网络覆盖区居民可办卡`, warn: false, tooltip: `${net} network 服务区内居民` };
    case "unknown":
      return { text: "办卡资格未知", warn: false, tooltip: "未确认" };
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
  const town = ctx?.town ?? "本馆所在镇";
  switch (r) {
    case "yes":
      if (scope === "town")
        return { text: `⚠ 取券仅限 ${town} 居民`, warn: true };
      return { text: "⚠ 取券有居住地限制", warn: true };
    case "no":
      return { text: "取券无居住地限制", warn: false };
    case "unknown":
    default:
      return { text: "取券限制未知 (未探测)", warn: false };
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
      return v != null ? `${v}% off` : "% off";
    case "free":
      return "FREE";
    case "dollars-off":
    case "dollar-off":
      return v != null ? `$${v} off` : "$ off";
    case "fixed-price":
      return v != null ? `$${v}/人` : "固定价";
    case "fixed-total":
      return v != null ? `共 $${v}` : "固定总价";
    case "bogo":
      return "买一送一";
    default:
      return [p.form, v].filter((x) => x !== undefined && x !== null && x !== "").join(" ").trim() || "—";
  }
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
