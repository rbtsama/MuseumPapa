import type { AgeRange, AudiencePolicy, Coupon, CouponCapacity } from '../data/types';

interface Props {
  coupon: Coupon;
  align?: 'left' | 'right';
}

type AudienceBucket = 'Adult' | 'Youth' | 'Child' | 'Everyone';

// Coupon-side audiences collapse to 4 buckets. Senior/Student/Educator/Military
// are attraction-side identity tiers; on the coupon they all fold into Adult.
// Vehicle / Single ticket aren't admission audiences — handled as special rows.
function bucket(audience: AudiencePolicy['audience']): AudienceBucket | null {
  switch (audience) {
    case 'Adult':
    case 'Senior':           return 'Adult';
    case 'Child':            return 'Child';
    case 'Youth':            return 'Youth';
    case 'Everyone':         return 'Everyone';
    case 'Vehicle':
    case 'Single ticket':    return null;
    default:                 return null;
  }
}

function fmtAmount(p: AudiencePolicy): string {
  switch (p.form) {
    case 'free': return 'FREE';
    case 'percent-off': return p.value != null ? `${p.value}% off` : 'discount';
    case 'dollar-off': return p.value != null ? `$${p.value} off` : 'discount';
    case 'per-person-price': return p.value != null ? `$${p.value}` : 'discount';
    case 'discount': return 'discount';
  }
}

// Adult ≥18, Senior ≥65, Youth <18, Child <18 are the bucket-implicit defaults;
// suppress age ranges that just restate them. Narrow tiers (Adult 13+ at JFK,
// Child age<6 at MFA, Youth age 7-17) survive.
function isRedundantAge(b: AudienceBucket, audience: AudiencePolicy['audience'], age: AgeRange): boolean {
  const { min, max } = age;
  if (b === 'Adult' && max == null && min != null && min >= 18 && min <= 19) return true;
  if (b === 'Adult' && audience === 'Senior') return true;
  if ((b === 'Youth' || b === 'Child') && min == null && max != null && max >= 17 && max <= 18) return true;
  if (b === 'Youth' && min === 13 && max === 17) return true;
  return false;
}

function fmtAudienceLabel(p: AudiencePolicy): string | null {
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

function PersonIcon() {
  // viewBox cropped from 0-24 to 4-20 (drops natural padding around the figure
  // so a row of icons sits flush). Render width is 9px; combined with negative
  // letter-spacing on the wrapper they overlap into a tight cluster.
  return (
    <svg width="9" height="11" viewBox="4 0 16 24" fill="currentColor" aria-hidden
      style={{ display: 'inline-block', verticalAlign: '-1px' }}>
      <path d="M7.5 6a4.5 4.5 0 1 1 9 0 4.5 4.5 0 0 1-9 0zM3.75 20.1a8.25 8.25 0 0 1 16.5 0 .75.75 0 0 1-.44.69 18.7 18.7 0 0 1-7.81 1.7c-2.79 0-5.43-.6-7.81-1.7a.75.75 0 0 1-.44-.69z" />
    </svg>
  );
}

function CapacityNode({ capacity, color }: { capacity: CouponCapacity; color: string }) {
  // people and ticket are both headcount-limited; render identically.
  // Single-ticket coupons (JFK Library) admit one person — same UX as people-n=1.
  if (capacity.n == null || capacity.n <= 0) return null;
  if (capacity.kind === 'people' || capacity.kind === 'ticket') {
    return (
      <span className="inline-flex items-baseline" style={{ color, gap: 3 }}>
        <span>up to</span>
        <span className="inline-flex items-center" style={{ gap: 0 }}>
          {Array.from({ length: capacity.n }).map((_, i) => <PersonIcon key={i} />)}
        </span>
      </span>
    );
  }
  return null;
}

// A coupon is "non-admission" when any policy carries vehicle as the unit.
// Display it as a single dim line so it doesn't get compared against admission discounts.
function isNonAdmissionCoupon(coupon: Coupon): boolean {
  if (coupon.capacity.kind === 'vehicle') return true;
  return coupon.audience_policies.some(p => p.audience === 'Vehicle');
}

export function CouponLine({ coupon, align = 'right' }: Props) {
  if (!coupon.audience_policies.length) return null;

  const dim = 'var(--ink-3)';
  const amount = 'var(--g)';
  const justify = align === 'right' ? 'justify-end' : 'justify-start';

  if (isNonAdmissionCoupon(coupon)) {
    return (
      <span style={{ fontSize: 12, color: dim, lineHeight: 1.2 }}>
        Parking Discount
      </span>
    );
  }

  const hasCapacity = coupon.capacity.n != null && coupon.capacity.n > 0
    && coupon.capacity.kind !== 'vehicle';

  return (
    <span
      className={`inline-flex flex-wrap items-baseline gap-x-1.5 gap-y-0.5 ${justify}`}
      style={{ fontSize: 12, lineHeight: 1.2 }}
    >
      {hasCapacity && <CapacityNode capacity={coupon.capacity} color={dim} />}
      {coupon.audience_policies.map((p, i) => {
        const label = fmtAudienceLabel(p);
        return (
          <span key={i} className="inline-flex items-baseline gap-1">
            {(i > 0 || hasCapacity) && <span style={{ color: dim }}>·</span>}
            <span style={{ color: amount, fontWeight: 700, fontSize: 13 }}>{fmtAmount(p)}</span>
            {label && <span style={{ color: dim }}>{label}</span>}
          </span>
        );
      })}
    </span>
  );
}
