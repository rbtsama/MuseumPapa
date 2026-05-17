import type { Coupon } from '../data/types';

interface Props {
  coupon: Coupon;
}

const SUMMARY_STYLE: React.CSSProperties = {
  fontSize: 14, fontWeight: 600, color: 'var(--g)', lineHeight: 1.2,
};

export function CouponLine({ coupon }: Props) {
  if (!coupon.summary) return null;
  return (
    <div className="text-right flex-shrink-0">
      <span style={SUMMARY_STYLE}>{coupon.summary}</span>
    </div>
  );
}
