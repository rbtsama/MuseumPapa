import type { Coupon, CouponForm } from '../data/types';

const STRENGTH: Record<CouponForm, number> = {
  free: 6,
  'percent-off': 5,
  'dollar-off': 4,
  'per-person-price': 3,
  discount: 2,
  bogo: 1,
};

export const couponStrength = (f: CouponForm): number => STRENGTH[f] ?? 0;

export function couponSummary(c: Coupon | null): string {
  if (!c) return '优惠详情未知';
  if (c.summary) return c.summary;
  const p = c.audience_policies[0];
  if (!p) return '优惠详情未知';
  switch (p.form) {
    case 'free': return 'FREE';
    case 'percent-off': return `${p.value ?? ''}% off`;
    case 'dollar-off': return `$${p.value ?? ''} off`;
    case 'per-person-price': return `$${p.value ?? ''}/人`;
    case 'bogo': return '买一送一';
    default: return '折扣';
  }
}

export function passStrength(c: Coupon | null): number {
  if (!c || !c.audience_policies.length) return 0;
  return Math.max(...c.audience_policies.map(p => couponStrength(p.form)));
}
