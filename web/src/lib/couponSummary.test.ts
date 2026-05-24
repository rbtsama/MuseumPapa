import { describe, it, expect } from 'vitest';
import { couponSummary, couponStrength } from './couponSummary';
describe('couponSummary', () => {
  it('uses backend summary when present', () => {
    expect(couponSummary({ capacity:{kind:'people',n:4}, audience_policies:[{audience:'Everyone',form:'percent-off',value:50}], summary:'50% off' })).toBe('50% off');
  });
  it('free strongest, bogo weakest in strength order', () => {
    expect(couponStrength('free')).toBeGreaterThan(couponStrength('percent-off'));
    expect(couponStrength('percent-off')).toBeGreaterThan(couponStrength('bogo'));
  });
  it('null coupon -> placeholder', () => { expect(couponSummary(null)).toBe('Discount details unavailable'); });
});
