import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { CouponLine } from './CouponLine';
import type { AudiencePolicy, Coupon, CouponCapacity } from '../data/types';

const make = (
  policies: AudiencePolicy[],
  capacity: CouponCapacity = { kind: 'people', n: 4 },
): Coupon => ({
  capacity,
  audience_policies: policies,
});

describe('CouponLine', () => {
  it('always shows the Everyone label so the audience is never ambiguous', () => {
    render(<CouponLine coupon={make([
      { audience: 'Everyone', age_range: null, count: null, form: 'per-person-price', value: 10 },
    ], { kind: 'people', n: 2 })} />);
    expect(screen.getByText('$10')).toBeInTheDocument();
    expect(screen.getByText('Everyone')).toBeInTheDocument();
  });

  it('uses mathematical age notation when an age range is present', () => {
    render(<CouponLine coupon={make([
      { audience: 'Child', age_range: { min: null, max: 5  }, count: null, form: 'free',             value: null },
      { audience: 'Youth', age_range: { min: 7,    max: 17 }, count: null, form: 'per-person-price', value: 5    },
      { audience: 'Adult', age_range: { min: 13,   max: null }, count: null, form: 'per-person-price', value: 10 },
    ])} />);
    expect(screen.getByText('age<6')).toBeInTheDocument();
    expect(screen.getByText('age 7-17')).toBeInTheDocument();
    expect(screen.getByText('age>=13')).toBeInTheDocument();
  });

  it('folds Senior into Adult and drops the redundant age tag', () => {
    render(<CouponLine coupon={make([
      { audience: 'Senior', age_range: { min: 65, max: null }, count: null, form: 'per-person-price', value: 17 },
    ])} />);
    expect(screen.getByText('Adult')).toBeInTheDocument();
    expect(screen.queryByText('Senior')).toBeNull();
    expect(screen.queryByText(/65/)).toBeNull();
  });

  it('keeps Child and Youth as distinct buckets when no age range is given', () => {
    render(<CouponLine coupon={make([
      { audience: 'Child', age_range: null, count: null, form: 'free',             value: null },
      { audience: 'Youth', age_range: null, count: null, form: 'per-person-price', value: 5    },
    ])} />);
    expect(screen.getByText('Child')).toBeInTheDocument();
    expect(screen.getByText('Youth')).toBeInTheDocument();
  });

  it('suppresses age ranges that just restate the bucket default', () => {
    render(<CouponLine coupon={make([
      { audience: 'Adult', age_range: { min: 18,   max: null }, count: null, form: 'free', value: null },
      { audience: 'Child', age_range: { min: null, max: 17   }, count: null, form: 'free', value: null },
      { audience: 'Youth', age_range: { min: 13,   max: 17   }, count: null, form: 'free', value: null },
    ])} />);
    expect(screen.queryByText(/age</)).toBeNull();
    expect(screen.queryByText(/age>=/)).toBeNull();
    expect(screen.queryByText(/age \d+-\d+/)).toBeNull();
  });

  it('renders parking coupons as a single dim "Other discount · parking" line', () => {
    render(<CouponLine coupon={make([
      { audience: 'Vehicle', age_range: null, count: null, form: 'free', value: null },
    ], { kind: 'vehicle', n: 1 })} />);
    expect(screen.getByText(/Other discount · parking/)).toBeInTheDocument();
    expect(screen.queryByText('FREE')).toBeNull();
  });

  it('preserves the bare "discount" word when a value is missing', () => {
    render(<CouponLine coupon={make([
      { audience: 'Everyone', age_range: null, count: null, form: 'discount', value: null },
    ])} />);
    expect(screen.getByText('discount')).toBeInTheDocument();
  });

  it('renders nothing when there are no audience_policies', () => {
    const { container } = render(<CouponLine coupon={{
      capacity: { kind: 'unspecified', n: null }, audience_policies: [],
    }} />);
    expect(container.firstChild).toBeNull();
  });

  it('emits N person-icon SVGs when capacity.kind = people', () => {
    const { container } = render(<CouponLine coupon={make([
      { audience: 'Everyone', age_range: null, count: null, form: 'free', value: null },
    ], { kind: 'people', n: 4 })} />);
    expect(container.querySelectorAll('svg').length).toBe(4);
  });
});
