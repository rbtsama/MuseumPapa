import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { CouponLine } from './CouponLine';
import type { AudiencePolicy, Coupon } from '../data/types';

const make = (
  policies: AudiencePolicy[],
  capacityN: number | null = 4,
): Coupon => ({
  capacity: { kind: 'people', n: capacityN },
  audience_policies: policies,
  summary: '',
});

describe('CouponLine', () => {
  it('hides the Everyone label when it is the only audience', () => {
    render(<CouponLine coupon={make([
      { audience: 'Everyone', age_range: null, count: null, form: 'free', value: null },
    ])} />);
    expect(screen.getByText('FREE')).toBeInTheDocument();
    expect(screen.queryByText('Everyone')).toBeNull();
  });

  it('renders amount + audience separately for tiered policies', () => {
    render(<CouponLine coupon={make([
      { audience: 'Adult', age_range: null, count: null, form: 'per-person-price', value: 5 },
      { audience: 'Child', age_range: { min: null, max: 17 }, count: null, form: 'free', value: null },
    ])} />);
    expect(screen.getByText('$5')).toBeInTheDocument();
    expect(screen.getByText('Adult')).toBeInTheDocument();
    expect(screen.getByText('FREE')).toBeInTheDocument();
    expect(screen.getByText('Child <18')).toBeInTheDocument();
  });

  it('formats percent-off and dollar-off amounts', () => {
    render(<CouponLine coupon={make([
      { audience: 'Everyone', age_range: null, count: null, form: 'percent-off', value: 50 },
    ])} />);
    expect(screen.getByText('50% off')).toBeInTheDocument();
  });

  it('renders nothing when there are no audience_policies', () => {
    const { container } = render(<CouponLine coupon={{
      capacity: { kind: 'unspecified', n: null }, audience_policies: [], summary: '',
    }} />);
    expect(container.firstChild).toBeNull();
  });

  it('omits capacity icons when n is null', () => {
    const { container } = render(<CouponLine coupon={make([
      { audience: 'Everyone', age_range: null, count: null, form: 'free', value: null },
    ], null)} />);
    expect(container.querySelector('svg')).toBeNull();
  });

  it('emits N person-icon SVGs when capacity.kind = people', () => {
    const { container } = render(<CouponLine coupon={make([
      { audience: 'Everyone', age_range: null, count: null, form: 'free', value: null },
    ], 4)} />);
    expect(container.querySelectorAll('svg').length).toBe(4);
  });
});
