import type { AudiencePolicy, Coupon } from '../data/types';

interface Props {
  coupon: Coupon;
}

function audienceLabel(p: AudiencePolicy): string | null {
  const a = p.audience;
  if (a === 'Vehicle' || a === 'Single ticket') return null;
  if (a === 'Child' && p.age_range?.max != null && p.age_range.max <= 5) {
    return `<${p.age_range.max + 1}`;
  }
  if (a === 'Senior') return 'Adult';
  return a;
}

function valueLabel(p: AudiencePolicy): string {
  switch (p.form) {
    case 'free': return 'FREE';
    case 'percent-off': return p.value != null ? `${p.value}% off` : 'discount';
    case 'dollar-off': return p.value != null ? `$${p.value} off` : 'discount';
    case 'per-person-price': return p.value != null ? `$${p.value}/person` : 'discount';
    case 'discount': return 'discount';
  }
}

export function AudienceValueLine({ coupon }: Props) {
  const policies = coupon.audience_policies
    .map(p => ({ aud: audienceLabel(p), val: valueLabel(p) }))
    .filter((x): x is { aud: string; val: string } => x.aud !== null);

  const showCapacity =
    coupon.capacity?.kind === 'people' && typeof coupon.capacity.n === 'number' && coupon.capacity.n > 0;

  return (
    <span
      className="font-serif"
      style={{ fontSize: 12, lineHeight: 1.35, fontWeight: 600, color: 'var(--g)' }}
    >
      {policies.map((p, i) => (
        <span key={i}>
          {i > 0 && <span style={{ color: 'var(--ink-3)', fontWeight: 400 }}> · </span>}
          {p.aud}{' '}
          <span style={{ color: 'var(--ink-2)', fontWeight: 700 }}>{p.val}</span>
        </span>
      ))}
      {showCapacity && (
        <span style={{ color: 'var(--ink-3)', fontWeight: 400 }}>
          {' · '}up to {coupon.capacity.n}
        </span>
      )}
    </span>
  );
}
