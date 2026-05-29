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
      return { cellIcon: "", icon: "✉", short: "Email", tooltip: "Emailed digital voucher — sent automatically after booking" };
    case "physical_coupon":
      return { cellIcon: "★", icon: "★", short: "Pickup", tooltip: "Pick up a paper voucher at the library — keep it (no return)" };
    case "physical_circ":
      return { cellIcon: "★★", icon: "★★", short: "Pickup & return", tooltip: "Borrow a physical pass — must be returned after use" };
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
      return { dot: "🟢", text: net, tone: "g" as const };
    case "own_card_only":
      return { dot: "🔴", text: town, tone: "rd" as const };
    case "ambiguous":
      return { dot: "🟠", text: "Ambiguous", tone: "or" as const };
    case "not_verified":
    default:
      return { dot: "⚪", text: "Not verified", tone: "ink-3" as const };
  }
}

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
      if (scope === "town") return { text: `${town} Resident`, warn: true };
      if (scope === "ma") return { text: "MA Resident", warn: true };
      return { text: "Restricted", warn: true };
    case "no":
      return { text: "—", warn: false };
    case "unknown":
    default:
      return { text: "—", warn: false };
  }
}


// ── monthly booking-frequency limit (mostly free text, rarely set) ───────
export function frequencyLimit(s: string | null | undefined): string | null {
  if (!s) return null;
  return s; // raw verbatim — never inject our own number
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
  adult: "Adult",
  child: "Child",
  children: "Children",
  senior: "Senior",
  youth: "Youth",
  student: "Student",
  military: "Military",
  veteran: "Veteran",
  educator: "Educator",
  teacher: "Teacher",
  family: "Family",
  everyone: "Everyone",
  infant: "Infant",
  toddler: "Toddler",
  preschool: "Preschool",
  resident: "Resident",
  member: "Member",
  group: "Group",
};
export function audienceLabel(a: string): string {
  if (!a) return "";
  return AUDIENCE_LABEL[a.toLowerCase()] || (a.charAt(0).toUpperCase() + a.slice(1));
}

// Format an age-range hint for a price/policy row.
//   { min: 0, max: 2 }   → "0–2"
//   { min: 62 }          → "62+"
//   { max: 12 }          → "≤12"
//   null / empty         → ""
export function ageRangeLabel(r?: { min: number | null; max: number | null } | null): string {
  if (!r) return "";
  const { min, max } = r;
  if (min != null && max != null) return `${min}–${max}`;
  if (min != null) return `${min}+`;
  if (max != null) return `≤${max}`;
  return "";
}

// One ticket-price line: friendly audience name + age range + price/Free.
export function priceLine(p: {
  audience: string;
  price: number | null;
  age_range?: { min: number | null; max: number | null } | null;
}): { label: string; value: string; isFree: boolean } {
  const aud = audienceLabel(p.audience);
  const range = ageRangeLabel(p.age_range);
  const label = range ? `${aud} ${range}` : aud;
  const isFree = p.price === 0;
  const value = isFree ? "Free" : p.price == null ? "—" : `$${p.price}`;
  return { label, value, isFree };
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
      return "Free";
    case "dollars-off":
    case "dollar-off":
      return v != null ? `$${v} off` : "$ off";
    case "fixed-price":
    case "per-person-price":
      return v != null ? `$${v} / person` : "Fixed price";
    case "fixed-total":
      return v != null ? `$${v} total` : "Fixed total";
    case "bogo":
      return "Buy 1 get 1";
    default:
      // Unknown form — surface what we have so a missing case is visible
      // (rather than silently saying "—"). Form names are kebab-case enum
      // values like "per-pass-discount"; humanize them so users see a
      // readable phrase instead of raw enum text.
      if (p.form) {
        const human = p.form.replace(/-/g, " ");
        return v != null ? `${human}: ${v}` : human;
      }
      return v != null ? String(v) : "—";
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
    adult:    "adult",
    senior:   "senior",
    child:    "child",
    children: "child",
    youth:    "youth",
    student:  "student",
    infant:   "infant",
    everyone: "person",
    family:   "family",
    military: "military",
  };
  const parts = withCount.map((p) => {
    const aud = (p.audience || "").toLowerCase();
    const tag = audMap[aud] || p.audience;
    // Pluralize when count > 1 (simple s-suffix — every term above pluralizes
    // regularly except "child" → "children").
    const n = p.count!;
    const word = n === 1
      ? tag
      : tag === "child" ? "children"
      : `${tag}s`;
    return `${n} ${word}`;
  });
  return { total, parts };
}
export function policyRange(p: AudiencePolicy): string {
  if (!p.age_range || (p.age_range.min == null && p.age_range.max == null)) return "";
  const { min, max } = p.age_range;
  if (min != null && max != null) return ` (ages ${min}–${max})`;
  if (min != null) return ` (ages ${min}+)`;
  if (max != null) return ` (under ${max + 1})`;
  return "";
}

// ── compact weekly hours ─────────────────────────────────────────────────
// Squash a 7-day hours dict into runs of consecutive days that share the same
// time string. Output is a list of human-readable strings the caller renders
// however they like (one chip per run, comma list, etc.).
//
// Example:
//   { mon:"09:00-21:00", tue:"09:00-21:00", wed:"09:00-21:00", thu:"09:00-21:00",
//     fri:"09:00-17:00", sat:"09:00-17:00", sun:"closed" }
//   →
//   [
//     { days: "Mon–Thu", value: "9 AM – 9 PM" },
//     { days: "Fri–Sat", value: "9 AM – 5 PM" },
//     { days: "Sun",     value: "Closed" },
//   ]
const _WEEK = ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"] as const;
const _ABBR: Record<typeof _WEEK[number], string> = {
  monday: "Mon", tuesday: "Tue", wednesday: "Wed", thursday: "Thu",
  friday: "Fri", saturday: "Sat", sunday: "Sun",
};

function _formatHour(h: string): string {
  // "HH:MM" → "H AM" / "H PM" / "H:MM AM". Trims an unnecessary :00.
  const [hh, mm] = h.split(":").map(Number);
  if (Number.isNaN(hh)) return h;
  const period = hh >= 12 ? "PM" : "AM";
  const hr = ((hh + 11) % 12) + 1;
  return mm === 0 ? `${hr} ${period}` : `${hr}:${String(mm).padStart(2, "0")} ${period}`;
}

function _formatHoursValue(raw: string): string {
  const v = (raw || "").trim().toLowerCase();
  if (!v || v === "—") return "—";
  if (v === "closed") return "Closed";
  if (v === "unknown") return "—";
  // Accept "HH:MM-HH:MM" or "HH:MM–HH:MM"
  const m = v.match(/^(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})$/);
  if (!m) return raw;
  return `${_formatHour(m[1])} – ${_formatHour(m[2])}`;
}

export function compactHours(hours: Partial<Record<typeof _WEEK[number], string>> | null | undefined):
  Array<{ days: string; value: string }> {
  if (!hours) return [];
  const runs: Array<{ days: string; value: string; startIdx: number; endIdx: number }> = [];
  for (let i = 0; i < _WEEK.length; i++) {
    const day = _WEEK[i];
    const raw = (hours[day] || "").trim();
    const pretty = _formatHoursValue(raw);
    const prev = runs[runs.length - 1];
    if (prev && prev.value === pretty && prev.endIdx === i - 1) {
      prev.endIdx = i;
      prev.days = prev.startIdx === prev.endIdx
        ? _ABBR[_WEEK[prev.startIdx]]
        : `${_ABBR[_WEEK[prev.startIdx]]}–${_ABBR[_WEEK[prev.endIdx]]}`;
    } else {
      runs.push({
        days: _ABBR[day],
        value: pretty,
        startIdx: i, endIdx: i,
      });
    }
  }
  return runs.map(({ days, value }) => ({ days, value }));
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
