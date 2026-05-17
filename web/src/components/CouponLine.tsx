import type { AgeRange, AudiencePolicy, Coupon, CouponCapacity } from '../data/types';

interface Props {
  coupon: Coupon;
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

// Age range is only worth showing when it tells the user something the audience
// label doesn't already imply. "Child <18", "Adult 18+", "Senior 65+", "Youth 13-17"
// all just restate the audience — drop them. Narrow tiers like "Child <6" or
// "Adult 13+" carry real semantic value — keep them.
function isRedundantAge(audience: AudiencePolicy['audience'], age: AgeRange): boolean {
  const { min, max } = age;
  if (audience === 'Adult'  && max == null && min != null && min >= 18 && min <= 19) return true;
  if (audience === 'Child'  && min == null && max != null && max >= 17 && max <= 18) return true;
  if (audience === 'Senior' && max == null && min != null && min >= 60 && min <= 65) return true;
  if (audience === 'Youth'  && min == null && max != null && max >= 17 && max <= 18) return true;
  if (audience === 'Youth'  && min === 13 && max === 17) return true;
  return false;
}

function fmtAudience(audience: AudiencePolicy['audience'], age: AgeRange | null): string {
  if (!age || isRedundantAge(audience, age)) return audience;
  const { min, max } = age;
  if (min != null && max != null) return `${audience} ${min}-${max}`;
  if (max != null) return `${audience} <${max + 1}`;
  if (min != null) return `${audience} ${min}+`;
  return audience;
}

// Heroicons "user" solid — round head + smooth shoulder silhouette, tighter than a stick figure.
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
  const hideAudienceLabel =
    coupon.audience_policies.length === 1 &&
    coupon.audience_policies[0].audience === 'Everyone';

  return (
    <span
      className="inline-flex flex-wrap items-baseline justify-end gap-x-1.5 gap-y-0.5"
      style={{ fontSize: 12, lineHeight: 1.2 }}
    >
      {hasCapacity && <CapacityNode capacity={coupon.capacity} color={dim} />}
      {coupon.audience_policies.map((p, i) => (
        <span key={i} className="inline-flex items-baseline gap-1">
          {(i > 0 || hasCapacity) && <span style={{ color: dim }}>·</span>}
          <span style={{ color: amount, fontWeight: 700, fontSize: 13 }}>{fmtAmount(p)}</span>
          {!hideAudienceLabel && (
            <span style={{ color: dim }}>{fmtAudience(p.audience, p.age_range)}</span>
          )}
        </span>
      ))}
    </span>
  );
}
