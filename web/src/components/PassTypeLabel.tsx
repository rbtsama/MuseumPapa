import type { PassTypeKind } from '../data/types';

/**
 * Small colored text label for the three pass types.
 *
 * Color gradient (calm → cautious — what UX feels increasingly inconvenient):
 *   - Online           = forest green (calm, instant, no friction)
 *   - Pickup           = amber (some friction, you drive once)
 *   - Pickup & Return  = orange (most friction, you drive twice)
 *
 * Same hue family so the page isn't noisy, but distinguishable.
 */
const META: Record<PassTypeKind, { label: string; fg: string; bg: string }> = {
  'digital':         { label: 'Email',            fg: 'var(--g)',  bg: 'var(--g-pale)'  },
  'physical-coupon': { label: 'Pickup',           fg: 'var(--au)', bg: 'var(--au-pale)' },
  'physical-circ':   { label: 'Pickup & Return',  fg: 'var(--or)', bg: 'var(--or-pale)' },
  'unknown':         { label: 'Pass',             fg: 'var(--ink-3)', bg: 'var(--paper)' },
};

interface Props {
  type: PassTypeKind;
}

export function PassTypeLabel({ type }: Props) {
  const m = META[type] ?? META.unknown;
  return (
    <span
      className="inline-block whitespace-nowrap"
      style={{
        background: m.bg,
        color: m.fg,
        fontSize: 11,
        fontWeight: 500,
        padding: '2px 7px',
        borderRadius: 3,
        lineHeight: 1.35,
      }}
    >
      {m.label}
    </span>
  );
}
