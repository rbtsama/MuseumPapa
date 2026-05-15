import type { Discount, OriginalPrice } from '../data/types';

/**
 * Eye-catching savings badge (red pill, white text) shown on each option row
 * to mirror the Trip.com / Booking.com "5% off" pattern that makes the
 * discount magnitude pop. Distinct from the PassTypeLabel (which classifies
 * the channel) — this badge advertises VALUE.
 */
interface Props {
  discount: Discount;
  originalPrice?: OriginalPrice | null;
}

function compute(discount: Discount, original: OriginalPrice | null | undefined): string | null {
  switch (discount.class) {
    case 'free':
      return 'FREE';
    case 'half':
      return '50% OFF';
    case 'percent-off': {
      const m = discount.label.match(/(\d+(?:\.\d+)?)%/);
      return m ? `${m[1]}% OFF` : 'DISCOUNT';
    }
    case 'dollar-off': {
      const m = discount.label.match(/\$(\d+(?:\.\d+)?)/);
      return m ? `$${m[1]} OFF` : 'DISCOUNT';
    }
    case 'price': {
      // Show implied savings if we know the original
      const m = discount.label.match(/\$(\d+(?:\.\d+)?)/);
      if (!m) return 'DEAL';
      const newPrice = parseFloat(m[1]);
      if (original?.adult != null && original.adult > newPrice) {
        const pct = Math.round((1 - newPrice / original.adult) * 100);
        return `${pct}% OFF`;
      }
      return `$${m[1]}`;
    }
    case 'discount':
      return 'DISCOUNT';
    default:
      return null;
  }
}

export function DiscountBadge({ discount, originalPrice }: Props) {
  const text = compute(discount, originalPrice);
  if (!text) return null;

  return (
    <span
      className="inline-block whitespace-nowrap"
      style={{
        background: 'var(--rd)',
        color: 'var(--white)',
        fontSize: 10,
        fontWeight: 700,
        padding: '2px 6px',
        borderRadius: 3,
        letterSpacing: '0.04em',
        lineHeight: 1.3,
      }}
    >
      {text}
    </span>
  );
}
