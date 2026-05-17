import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { CouponLine } from './CouponLine';
import type { Coupon } from '../data/types';

const make = (summary: string): Coupon => ({
  capacity: { kind: 'people', n: 4 },
  audience_policies: [{ audience: 'Everyone', age_range: null, count: null, form: 'free', value: null }],
  summary,
});

describe('CouponLine', () => {
  it('renders FREE summary', () => {
    render(<CouponLine coupon={make('Up to 4 · FREE')} />);
    expect(screen.getByText('Up to 4 · FREE')).toBeInTheDocument();
  });

  it('renders percent-off summary', () => {
    render(<CouponLine coupon={make('Up to 4 · 50% off')} />);
    expect(screen.getByText('Up to 4 · 50% off')).toBeInTheDocument();
  });

  it('renders per-person price summary', () => {
    render(<CouponLine coupon={make('Up to 4 · $9/person')} />);
    expect(screen.getByText('Up to 4 · $9/person')).toBeInTheDocument();
  });

  it('renders nothing when summary is empty', () => {
    const { container } = render(<CouponLine coupon={make('')} />);
    expect(container.firstChild).toBeNull();
  });
});
