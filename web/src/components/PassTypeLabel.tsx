import type { PassTypeKind } from '../data/types';

/**
 * Small colored text label for the three pass types.
 *
 * Color gradient (calm → cautious — what UX feels increasingly inconvenient):
 *   - Email   = forest green (calm, instant, no friction)
 *   - Pickup  = amber (some friction, you drive once)
 *   - Pik&Rtn = orange (most friction, you drive twice — collect and return)
 *
 * Same hue family so the page isn't noisy, but distinguishable.
 */
const META: Record<PassTypeKind, { label: string; fg: string; bg: string }> = {
  'digital':         { label: 'Email',  fg: 'var(--g)',     bg: 'var(--g-pale)'  },
  'physical-coupon': { label: 'Pickup', fg: 'var(--au)',    bg: 'var(--au-pale)' },
  'physical-circ':   { label: 'Pik&Rtn', fg: 'var(--or)',    bg: 'var(--or-pale)' },
  'unknown':         { label: 'Pass',   fg: 'var(--ink-3)', bg: 'var(--paper)'   },
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
        // Thin border in the same color as the label text — makes the pill
        // crisper at small sizes than relying on the pale background alone.
        border: `1px solid ${m.fg}`,
        fontSize: 11,
        fontWeight: 500,
        padding: '1px 6px',     // 1px less than before to offset the border
        borderRadius: 3,
        lineHeight: 1.35,
      }}
    >
      {m.label}
    </span>
  );
}
