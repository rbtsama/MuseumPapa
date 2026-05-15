import type { PassTypeKind } from '../data/types';

interface Props {
  passType: PassTypeKind;
  discountLabel: string;      // e.g., "Free", "50% off", "$5 off"
  libraryTown?: string;       // shown for non-digital
  distanceMi?: number | null; // shown for non-digital if not null
}

const STYLE_BY_TYPE: Record<PassTypeKind, { bg: string; fg: string; icon: string }> = {
  'digital':         { bg: 'var(--g-pale)', fg: 'var(--g)',  icon: '⚡' },
  'physical-coupon': { bg: 'var(--au-pale)', fg: 'var(--au)', icon: '🎫' },
  'loan-card':       { bg: 'var(--or-pale)', fg: 'var(--or)', icon: '🔁' },
  'unknown':         { bg: 'var(--paper)',  fg: 'var(--ink-3)', icon: '?' },
};

export function PassTag({ passType, discountLabel, libraryTown, distanceMi }: Props) {
  const s = STYLE_BY_TYPE[passType];
  const showLocation = passType !== 'digital' && libraryTown;
  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: '4px',
      padding: '4px 9px',
      borderRadius: '3px',
      background: s.bg,
      color: s.fg,
      fontSize: '12px',
      whiteSpace: 'nowrap',
    }}>
      <span aria-hidden>{s.icon}</span>
      <span style={{ fontWeight: 500 }}>{discountLabel}</span>
      {showLocation && (
        <span style={{ color: 'var(--ink-3)', fontWeight: 400 }}>
          · {libraryTown}
          {distanceMi != null && ` ${Math.round(distanceMi)} mi`}
        </span>
      )}
    </span>
  );
}
