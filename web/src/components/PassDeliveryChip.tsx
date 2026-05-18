import type { Pass } from '../data/types';

interface Props {
  passType: Pass['pass_type'];
  distanceMi: number | null | undefined;
}

const BASE_STYLE: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: 3,
  padding: '2px 7px',
  borderRadius: 10,
  fontSize: 10,
  fontWeight: 600,
  textTransform: 'uppercase',
  letterSpacing: '0.04em',
  whiteSpace: 'nowrap',
};

export function PassDeliveryChip({ passType, distanceMi }: Props) {
  if (passType === 'digital') {
    return (
      <span style={{ ...BASE_STYLE, background: 'var(--g-pale)', color: 'var(--g)' }}>
        ✉ Email
      </span>
    );
  }

  const distSuffix = distanceMi != null ? ` ${Math.round(distanceMi)}mi` : '';

  if (passType === 'physical-coupon') {
    return (
      <span style={{ ...BASE_STYLE, background: 'var(--au-pale)', color: 'var(--au)' }}>
        📍 Pickup{distSuffix}
      </span>
    );
  }

  // physical-circ
  return (
    <span style={{ ...BASE_STYLE, background: 'var(--rd-pale)', color: 'var(--rd)' }}>
      🔄 Borrow{distSuffix}
    </span>
  );
}
