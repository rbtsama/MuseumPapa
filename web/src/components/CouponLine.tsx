import type { AgeRange, AudiencePolicy, Coupon, CouponCapacity } from '../data/types';

interface Props {
  coupon: Coupon;
  size?: 'sm' | 'md';
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

function fmtAudience(audience: AudiencePolicy['audience'], age: AgeRange | null): string {
  let ageTxt = '';
  if (age) {
    if (age.min != null && age.max != null) ageTxt = ` ${age.min}-${age.max}`;
    else if (age.max != null) ageTxt = ` <${age.max + 1}`;
    else if (age.min != null) ageTxt = ` ${age.min}+`;
  }
  return `${audience}${ageTxt}`;
}

function PersonIcon({ size }: { size: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="currentColor" aria-hidden>
      <circle cx="8" cy="4.5" r="2.6" />
      <path d="M2.5 14c0-3 2.5-5 5.5-5s5.5 2 5.5 5v.5H2.5z" />
    </svg>
  );
}

function CapacityIcons({ capacity, color, iconSize }: {
  capacity: CouponCapacity; color: string; iconSize: number;
}) {
  if (capacity.n == null || capacity.n <= 0) return null;
  if (capacity.kind === 'people') {
    return (
      <span className="inline-flex items-center gap-0.5" style={{ color }}>
        {Array.from({ length: capacity.n }).map((_, i) => (
          <PersonIcon key={i} size={iconSize} />
        ))}
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

export function CouponLine({ coupon, size = 'md' }: Props) {
  if (!coupon.audience_policies.length) return null;

  const fontSize = size === 'sm' ? 13 : 14;
  const iconSize = size === 'sm' ? 10 : 11;
  const dim = 'var(--ink-3)';
  const amount = 'var(--g)';

  const hideAudienceLabel =
    coupon.audience_policies.length === 1 &&
    coupon.audience_policies[0].audience === 'Everyone';

  const capacityNode = (
    <CapacityIcons capacity={coupon.capacity} color={dim} iconSize={iconSize} />
  );
  const hasCapacity = coupon.capacity.n != null && coupon.capacity.n > 0;

  return (
    <div className="text-right flex-shrink-0">
      <span
        className="inline-flex items-center gap-1.5 flex-wrap justify-end"
        style={{ fontSize, lineHeight: 1.2 }}
      >
        {hasCapacity && capacityNode}
        {coupon.audience_policies.map((p, i) => (
          <span key={i} className="inline-flex items-baseline gap-1">
            {(i > 0 || hasCapacity) && (
              <span style={{ color: dim }}>·</span>
            )}
            <span style={{ color: amount, fontWeight: 700 }}>{fmtAmount(p)}</span>
            {!hideAudienceLabel && (
              <span style={{ color: dim }}>{fmtAudience(p.audience, p.age_range)}</span>
            )}
          </span>
        ))}
      </span>
    </div>
  );
}
