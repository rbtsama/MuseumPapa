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
  it('always shows the Everyone label so the audience is never ambiguous', () => {
    render(<CouponLine coupon={make([
      { audience: 'Everyone', age_range: null, count: null, form: 'per-person-price', value: 10 },
    ], 2)} />);
    expect(screen.getByText('$10')).toBeInTheDocument();
    expect(screen.getByText('Everyone')).toBeInTheDocument();
  });

  it('renders amount + audience separately for tiered policies', () => {
    render(<CouponLine coupon={make([
      { audience: 'Adult', age_range: null, count: null, form: 'per-person-price', value: 5 },
      { audience: 'Child', age_range: { min: null, max: 5 }, count: null, form: 'free', value: null },
    ])} />);
    expect(screen.getByText('$5')).toBeInTheDocument();
    expect(screen.getByText('Adult')).toBeInTheDocument();
    expect(screen.getByText('FREE')).toBeInTheDocument();
    expect(screen.getByText('Youth <6')).toBeInTheDocument();
  });

  it('folds Senior into the Adult bucket', () => {
    render(<CouponLine coupon={make([
      { audience: 'Senior', age_range: { min: 65, max: null }, count: null, form: 'per-person-price', value: 17 },
    ])} />);
    expect(screen.getByText('Adult')).toBeInTheDocument();
    expect(screen.queryByText('Senior')).toBeNull();
    expect(screen.queryByText(/65\+/)).toBeNull();
  });

  it('folds Child into the Youth bucket', () => {
    render(<CouponLine coupon={make([
      { audience: 'Child', age_range: { min: null, max: 12 }, count: null, form: 'free', value: null },
    ])} />);
    expect(screen.getByText('Youth <13')).toBeInTheDocument();
    expect(screen.queryByText(/Child/)).toBeNull();
  });

  it('hides redundant age ranges that just restate the bucket', () => {
    render(<CouponLine coupon={make([
      { audience: 'Adult', age_range: { min: 18,   max: null }, count: null, form: 'free', value: null },
      { audience: 'Child', age_range: { min: null, max: 17   }, count: null, form: 'free', value: null },
      { audience: 'Youth', age_range: { min: 13,   max: 17   }, count: null, form: 'free', value: null },
    ])} />);
    expect(screen.getByText('Adult')).toBeInTheDocument();
    expect(screen.getAllByText('Youth').length).toBeGreaterThan(0);
    expect(screen.queryByText(/18\+/)).toBeNull();
    expect(screen.queryByText(/<18/)).toBeNull();
    expect(screen.queryByText(/13-17/)).toBeNull();
  });

  it('keeps narrow age ranges that carry real semantic value', () => {
    render(<CouponLine coupon={make([
      { audience: 'Adult', age_range: { min: 13,   max: null }, count: null, form: 'per-person-price', value: 10 },
      { audience: 'Child', age_range: { min: null, max: 5    }, count: null, form: 'free',             value: null },
      { audience: 'Youth', age_range: { min: 7,    max: 17   }, count: null, form: 'per-person-price', value: 5 },
    ])} />);
    expect(screen.getByText('Adult 13+')).toBeInTheDocument();
    expect(screen.getByText('Youth <6')).toBeInTheDocument();
    expect(screen.getByText('Youth 7-17')).toBeInTheDocument();
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
