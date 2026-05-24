import type { PassForm } from '../data/types';

/**
 * Small colored text label for the three pass forms.
 *
 * Color gradient (calm → cautious — what UX feels increasingly inconvenient):
 *   - digital_email  = forest green (calm, instant, no friction)
 *   - physical_coupon = amber (some friction — you print/show the coupon)
 *   - physical_circ  = orange (most friction — you pick up AND return the pass)
 *
 * Same hue family so the page isn't noisy, but distinguishable.
 */
const META: Record<PassForm, { label: string; fg: string; bg: string }> = {
  'digital_email':    { label: 'Email',    fg: 'var(--g)',     bg: 'var(--g-pale)'  },
  'physical_coupon':  { label: 'Coupon',   fg: 'var(--au)',    bg: 'var(--au-pale)' },
  'physical_circ':    { label: 'Pickup',   fg: 'var(--or)',    bg: 'var(--or-pale)' },
};

interface Props {
  type: PassForm;
}

export function PassTypeLabel({ type }: Props) {
  const m = META[type] ?? { label: 'Pass', fg: 'var(--ink-3)', bg: 'var(--paper)' };
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
