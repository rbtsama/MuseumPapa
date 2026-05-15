import { describe, it, expect } from 'vitest';
import { formatDiscount } from './discount-display';
import type { Discount, Policy } from '../data/types';

function d(klass: Discount['class'], label = ''): Discount {
  return { class: klass, label, raw: '' };
}
function p(partial: Partial<Policy>): Policy {
  return {
    max_people: null, max_adults: null, max_children: null, eligibility: null,
    free_under_age: null, savings_per_person_usd: null, notes: null, raw: null,
    ...partial,
  };
}

describe('formatDiscount', () => {
  it('free with no policy: Free, no qualifier, finalPrice=0', () => {
    const out = formatDiscount(d('free', 'Free'), null, 30);
    expect(out.primary).toBe('Free');
    expect(out.qualifier).toBeNull();
    expect(out.finalPrice).toBe(0);
    expect(out.originalPrice).toBe(30);
  });

  it('half off + max_people 4: 50% off · up to 4 people, NO dollar (policy uncertain)', () => {
    const out = formatDiscount(d('half', '50% off'), p({ max_people: 4 }), 30);
    expect(out.primary).toBe('50% off');
    expect(out.qualifier).toBe('up to 4 people');
    // per user decision: dollar shown only when uniform; max_people is uniform-per-adult, allowed
    expect(out.finalPrice).toBe(15);
  });

  it('half off + adults_only: qualifier "adults only", no dollar', () => {
    const out = formatDiscount(d('half', '50% off'), p({ eligibility: 'adults_only' }), 30);
    expect(out.qualifier).toBe('adults only');
    expect(out.finalPrice).toBeNull();
  });

  it('dollar-off + savings_per_person_usd: shows savings detail, NO dollar', () => {
    const out = formatDiscount(d('dollar-off', '$5 off'), p({ savings_per_person_usd: 5, max_people: 4 }), 30);
    expect(out.primary).toBe('$5 off');
    expect(out.qualifier).toBe('up to 4 people');
    expect(out.detail).toMatch(/\$5 per person/i);
    expect(out.finalPrice).toBeNull();
  });

  it('vehicle eligibility: qualifier "per vehicle", no dollar', () => {
    const out = formatDiscount(d('free', 'Free parking'), p({ eligibility: 'vehicle' }), 0);
    expect(out.qualifier).toBe('per vehicle');
    expect(out.finalPrice).toBeNull();
  });

  it('members eligibility: qualifier "members", no dollar', () => {
    const out = formatDiscount(d('free', 'Free'), p({ eligibility: 'members' }), 30);
    expect(out.qualifier).toBe('members');
    expect(out.finalPrice).toBeNull();
  });

  it('free_under_age in policy surfaces as detail', () => {
    const out = formatDiscount(d('half', '50% off'), p({ max_people: 4, free_under_age: 2 }), 30);
    expect(out.detail).toBe('Free under 2');
  });

  it('percent-off with no policy: dollar applied', () => {
    const out = formatDiscount(d('percent-off', '40% off'), null, 50);
    expect(out.finalPrice).toBe(30);
    expect(out.originalPrice).toBe(50);
  });

  it('no adult price: finalPrice always null', () => {
    const out = formatDiscount(d('half', '50% off'), null, null);
    expect(out.finalPrice).toBeNull();
    expect(out.originalPrice).toBeNull();
  });

  it('max_adults + max_children: combined qualifier', () => {
    const out = formatDiscount(d('free', 'Free'), p({ max_adults: 2, max_children: 2 }), null);
    expect(out.qualifier).toBe('2 adults + 2 kids');
  });
});
