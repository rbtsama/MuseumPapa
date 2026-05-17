import type { AgeRange, AudiencePolicy, Coupon, CouponCapacity } from '../data/types';

interface Props {
  coupon: Coupon;
}

type AudienceBucket = 'Adult' | 'Youth' | 'Everyone';

// Collapse the raw schema audiences into the three buckets the product uses.
// Senior/Student/Military/Educator fold into Adult; Child folds into Youth.
// Vehicle and Single-ticket aren't audiences — capacity carries their unit.
function bucket(audience: AudiencePolicy['audience']): AudienceBucket | null {
  switch (audience) {
    case 'Adult':
    case 'Senior':           return 'Adult';
    case 'Child':
    case 'Youth':            return 'Youth';
    case 'Everyone':         return 'Everyone';
    case 'Vehicle':
    case 'Single ticket':    return null;
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

// Age range is only worth showing when narrower than the bucket implies.
// Adult ≥18, Youth <18, Senior ≥65 are defaults — drop. Adult 13+ at JFK, Youth <6 at MFA — keep.
function isRedundantAge(b: AudienceBucket, audience: AudiencePolicy['audience'], age: AgeRange): boolean {
  const { min, max } = age;
  if (b === 'Adult' && max == null && min != null && min >= 18 && min <= 19) return true;
  if (b === 'Adult' && audience === 'Senior') return true;
  if (b === 'Youth' && min == null && max != null && max >= 17 && max <= 18) return true;
  if (b === 'Youth' && min === 13 && max === 17) return true;
  return false;
}

function fmtAudienceLabel(p: AudiencePolicy): string | null {
  const b = bucket(p.audience);
  if (b == null) return null;
  const age = p.age_range;
  if (!age || isRedundantAge(b, p.audience, age)) return b;
  const { min, max } = age;
  if (min != null && max != null) return `${b} ${min}-${max}`;
  if (max != null) return `${b} <${max + 1}`;
  if (min != null) return `${b} ${min}+`;
  return b;
}

function PersonIcon() {
  return (
    <svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor" aria-hidden
      style={{ display: 'inline-block', verticalAlign: '-1px' }}>
      <path d="M7.5 6a4.5 4.5 0 1 1 9 0 4.5 4.5 0 0 1-9 0zM3.75 20.1a8.25 8.25 0 0 1 16.5 0 .75.75 0 0 1-.44.69 18.7 18.7 0 0 1-7.81 1.7c-2.79 0-5.43-.6-7.81-1.7a.75.75 0 0 1-.44-.69z" />
    </svg>
  );
}

function CapacityNode({ capacity, color }: { capacity: CouponCapacity; color: string }) {
  if (capacity.n == null || capacity.n <= 0) return null;
  if (capacity.kind === 'people') {
    return (
      <span className="inline-flex items-baseline" style={{ color, gap: 3 }}>
        <span>up to</span>
        <span className="inline-flex items-center" style={{ gap: 1 }}>
          {Array.from({ length: capacity.n }).map((_, i) => <PersonIcon key={i} />)}
        </span>
      </span>
    );
  }
  if (capacity.kind === 'vehicle') {
    return <span style={{ color }}>{capacity.n} vehicle{capacity.n > 1 ? 's' : ''}</span>;
  }
  if (capacity.kind === 'ticket') {
    return <span style={{ color }}>{capacity.n} ticket{capacity.n > 1 ? 's' : ''}</span>;
  }
  return null;
}

export function CouponLine({ coupon }: Props) {
  if (!coupon.audience_policies.length) return null;

  const dim = 'var(--ink-3)';
  const amount = 'var(--g)';
  const hasCapacity = coupon.capacity.n != null && coupon.capacity.n > 0;

  return (
    <span
      className="inline-flex flex-wrap items-baseline justify-end gap-x-1.5 gap-y-0.5"
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
