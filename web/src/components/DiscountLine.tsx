import type { Discount, Policy } from '../data/types';
import { formatDiscount } from '../lib/discount-display';

interface Props {
  discount: Discount;
  policy: Policy | null;
  /** Adult price from attraction.original_price.adult, used for "$X → $Y" math. */
  adult: number | null;
}

const MONEY_STYLE: React.CSSProperties = {
  fontSize: 16, fontWeight: 700, color: 'var(--g)', lineHeight: 1.1,
};

function fmtMoney(v: number): string {
  if (v === 0) return 'Free';
  if (Number.isInteger(v)) return `$${v}`;
  return `$${v.toFixed(2)}`;
}

/**
 * Renders an option row's discount info, replacing the older inline "$30 → $15"
 * block. When the pass's policy doesn't allow a uniform dollar projection
 * (per-vehicle, per-person savings, adults_only, ...) we show the discount
 * label + party-cap qualifier instead. This avoids the misleading "$30 → $15"
 * for passes that actually mean "50% off, up to 4 people".
 */
export function DiscountLine({ discount, policy, adult }: Props) {
  const dd = formatDiscount(discount, policy, adult);

  return (
    <div className="text-right flex-shrink-0">
      {dd.finalPrice !== null ? (
        <div className="flex items-baseline gap-1.5 justify-end">
          {dd.originalPrice !== null && dd.originalPrice !== dd.finalPrice && (
            <span style={{ fontSize: 11, color: 'var(--ink-3)', textDecoration: 'line-through' }}>
              {fmtMoney(dd.originalPrice)}
            </span>
          )}
          <span style={MONEY_STYLE}>{fmtMoney(dd.finalPrice)}</span>
        </div>
      ) : (
        <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--g)' }}>{dd.primary}</span>
      )}
      {dd.qualifier && (
        <div style={{ fontSize: 10, color: 'var(--ink-3)', marginTop: 1 }}>{dd.qualifier}</div>
      )}
      {dd.detail && !dd.qualifier && (
        <div style={{ fontSize: 10, color: 'var(--ink-3)', marginTop: 1 }}>{dd.detail}</div>
      )}
    </div>
  );
}
