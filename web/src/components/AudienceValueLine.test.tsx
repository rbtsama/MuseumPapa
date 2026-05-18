import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { AudienceValueLine } from './AudienceValueLine';
import type { Coupon } from '../data/types';

function makeCoupon(over: Partial<Coupon> = {}): Coupon {
  return {
    capacity: { kind: 'people', n: 4 },
    audience_policies: [
      { audience: 'Adult', age_range: { min: null, max: null }, count: null, form: 'percent-off', value: 50 },
    ],
    ...over,
  };
}

describe('AudienceValueLine', () => {
  it('renders single policy with capacity', () => {
    const { container } = render(<AudienceValueLine coupon={makeCoupon()} />);
    const text = container.textContent ?? '';
    expect(text).toMatch(/Adult/);
    expect(text).toMatch(/50% off/);
    expect(text).toMatch(/up to 4/);
  });

  it('renders multi-policy stack', () => {
    const c = makeCoupon({
      audience_policies: [
        { audience: 'Adult', age_range: { min: null, max: null }, count: null, form: 'percent-off', value: 50 },
        { audience: 'Child', age_range: { min: null, max: null }, count: null, form: 'free', value: null },
      ],
    });
    const { container } = render(<AudienceValueLine coupon={c} />);
    const text = container.textContent ?? '';
    expect(text).toMatch(/Adult/);
    expect(text).toMatch(/50% off/);
    expect(text).toMatch(/Child/);
    expect(text).toMatch(/FREE/);
  });

  it('omits capacity when n is 0 or kind is not people', () => {
    const c = makeCoupon({ capacity: { kind: 'unspecified', n: null } });
    const { container } = render(<AudienceValueLine coupon={c} />);
    expect(container.textContent ?? '').not.toMatch(/up to/);
  });

  it('formats per-person-price as $N/person', () => {
    const c = makeCoupon({
      audience_policies: [
        { audience: 'Everyone', age_range: { min: null, max: null }, count: null, form: 'per-person-price', value: 8 },
      ],
    });
    expect(render(<AudienceValueLine coupon={c} />).container.textContent ?? '').toMatch(/\$8\/person/);
  });
});
