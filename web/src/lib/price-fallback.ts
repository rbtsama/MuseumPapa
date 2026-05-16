import type { OriginalPrice, Discount } from '../data/types';

/**
 * Compute the user's final price given original price and a discount.
 * Returns null if we can't compute (original missing).
 */
export function applyDiscount(original: OriginalPrice | null, discount: Discount): number | null {
  const adult = original?.age_pricing?.adult?.price ?? null;
  if (adult == null) return null;
  switch (discount.class) {
    case 'free': return 0;
    case 'half': return adult * 0.5;
    case 'dollar-off': {
      // Parse "$N off" from label
      const m = discount.label.match(/\$(\d+(?:\.\d+)?)/);
      return m ? Math.max(0, adult - parseFloat(m[1])) : null;
    }
    case 'percent-off': {
      const m = discount.label.match(/(\d+(?:\.\d+)?)%/);
      return m ? adult * (1 - parseFloat(m[1]) / 100) : null;
    }
    case 'price': {
      // Label is "$N per person" or similar — use it as the new price
      const m = discount.label.match(/\$(\d+(?:\.\d+)?)/);
      return m ? parseFloat(m[1]) : null;
    }
    default: return null;
  }
}

/**
 * Format an original price + discount into a display string for the card header:
 *   - "Original $30 → Free"
 *   - "Original $30 → $15 (50% off)"
 *   - "$5 off" (no original known)
 *   - "Free" (no original, but discount is genuinely free)
 *   - "" (no useful information)
 */
export function formatPriceLine(original: OriginalPrice | null, discount: Discount | null): string {
  const adult = original?.age_pricing?.adult?.price ?? null;
  if (!discount) {
    // No discount applicable — just show original
    if (adult != null) return `Original $${adult}`;
    return '';
  }
  const final = applyDiscount(original, discount);
  if (adult != null) {
    if (final === 0) return `Original $${adult} → Free`;
    if (final != null) {
      const finalStr = Number.isInteger(final) ? `$${final}` : `$${final.toFixed(2)}`;
      return `Original $${adult} → ${finalStr}`;
    }
    // can't compute final — at least show the discount label
    return `Original $${adult} (${discount.label})`;
  }
  // No original — just the discount label
  return discount.label;
}
