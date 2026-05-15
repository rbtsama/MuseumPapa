import type { Discount, Policy } from '../data/types';

export interface DiscountDisplay {
  /** Headline string, e.g. "50% off", "Free", "$15", "$5 off". */
  primary: string;
  /** Party-size or eligibility qualifier, e.g. "up to 4 people", "per vehicle". */
  qualifier: string | null;
  /** Footnote, e.g. "Free under 2", "Adults only". */
  detail: string | null;
  /** Resolved final dollar price when policy is uniform enough to be trustworthy. */
  finalPrice: number | null;
  /** Original "from" price the finalPrice was computed off, for strikethrough. */
  originalPrice: number | null;
}

const ELIGIBILITY_LABEL: Record<string, string> = {
  vehicle: 'per vehicle',
  adults_only: 'adults only',
  single_ticket: '1 ticket',
  members: 'members',
  seniors_free: 'seniors free',
  students_only: 'students only',
  weekday_only: 'weekdays only',
  blackout_dates: 'some dates excluded',
  reservation_required: 'reservation needed',
  id_required: 'ID at gate',
};

/** Apply a percent discount class to a base dollar amount when safe. */
function applyDiscountClass(klass: string, label: string, base: number): number | null {
  if (klass === 'free') return 0;
  if (klass === 'half') return Math.round(base * 0.5);
  if (klass === 'percent-off') {
    const m = label.match(/(\d+)\s*%/);
    if (m) return Math.round(base * (1 - parseInt(m[1], 10) / 100));
  }
  if (klass === 'dollar-off') {
    const m = label.match(/\$(\d+(?:\.\d+)?)/);
    if (m) return Math.max(0, base - parseFloat(m[1]));
  }
  if (klass === 'price') {
    const m = label.match(/\$(\d+(?:\.\d+)?)/);
    if (m) return parseFloat(m[1]);
  }
  return null;
}

/** Headline string from the discount itself, independent of policy. */
function primaryText(d: Discount): string {
  if (d.class === 'free') return 'Free';
  if (d.class === 'half') return '50% off';
  return d.label || 'Discount';
}

/** Qualifier string, when policy carries one. */
function qualifierText(policy: Policy | null): string | null {
  if (!policy) return null;
  const elig = policy.eligibility;
  if (elig && ELIGIBILITY_LABEL[elig]) return ELIGIBILITY_LABEL[elig];
  if (policy.max_adults && policy.max_children) {
    return `${policy.max_adults} adults + ${policy.max_children} kids`;
  }
  if (policy.max_people) return `up to ${policy.max_people} people`;
  return null;
}

/** Footnote string from policy extras. */
function detailText(policy: Policy | null): string | null {
  if (!policy) return null;
  if (policy.free_under_age) return `Free under ${policy.free_under_age}`;
  if (policy.savings_per_person_usd) return `save $${policy.savings_per_person_usd} per person`;
  if (policy.notes) return policy.notes;
  return null;
}

/**
 * Decide whether final $ price is trustworthy enough to show.
 * Rule: only when discount applies uniformly to the adult tier
 * (no party-size restriction, no per-person savings framing,
 * and either no eligibility or `all`).
 */
function policyAllowsDollar(policy: Policy | null): boolean {
  if (!policy) return true;  // no policy = treat as uniform
  if (policy.savings_per_person_usd !== null) return false;
  if (policy.eligibility && policy.eligibility !== 'all') return false;
  // party-size cap is fine for dollar (still applies per-adult), but per-vehicle / per-ticket not handled here
  return true;
}

export function formatDiscount(
  discount: Discount,
  policy: Policy | null,
  adultPrice: number | null,
): DiscountDisplay {
  const primary = primaryText(discount);
  const qualifier = qualifierText(policy);
  const detail = detailText(policy);

  let finalPrice: number | null = null;
  let originalPrice: number | null = null;
  if (adultPrice !== null && policyAllowsDollar(policy)) {
    const fp = applyDiscountClass(discount.class, discount.label, adultPrice);
    if (fp !== null) {
      finalPrice = fp;
      originalPrice = adultPrice;
    }
  }
  return { primary, qualifier, detail, finalPrice, originalPrice };
}
