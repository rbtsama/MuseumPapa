import { describe, it, expect } from 'vitest';
import { applyDiscount, formatPriceLine } from './price-fallback';
import type { OriginalPrice } from '../data/types';

const adult30: OriginalPrice = {
  adult: 30, child: null, senior: null, student: null, family: null,
  free_under_age: null, notes: null, source_url: null,
};

describe('applyDiscount', () => {
  it('free → 0', () => {
    expect(applyDiscount(adult30, { class: 'free', label: 'Free', raw: '' })).toBe(0);
  });
  it('half → 15', () => {
    expect(applyDiscount(adult30, { class: 'half', label: '50% off', raw: '' })).toBe(15);
  });
  it('$5 off → 25', () => {
    expect(applyDiscount(adult30, { class: 'dollar-off', label: '$5 off', raw: '' })).toBe(25);
  });
  it('20% off → 24', () => {
    expect(applyDiscount(adult30, { class: 'percent-off', label: '20% off', raw: '' })).toBe(24);
  });
  it('$5/person price → 5', () => {
    expect(applyDiscount(adult30, { class: 'price', label: '$5 per person', raw: '' })).toBe(5);
  });
  it('unknown discount → null', () => {
    expect(applyDiscount(adult30, { class: 'unknown', label: '', raw: '' })).toBeNull();
  });
  it('no original → null', () => {
    expect(applyDiscount(null, { class: 'free', label: 'Free', raw: '' })).toBeNull();
  });
});

describe('formatPriceLine', () => {
  it('original + free', () => {
    expect(formatPriceLine(adult30, { class: 'free', label: 'Free', raw: '' }))
      .toBe('Original $30 → Free');
  });
  it('original + half', () => {
    expect(formatPriceLine(adult30, { class: 'half', label: '50% off', raw: '' }))
      .toBe('Original $30 → $15');
  });
  it('no original + free', () => {
    expect(formatPriceLine(null, { class: 'free', label: 'Free', raw: '' }))
      .toBe('Free');
  });
  it('no original + $5 off', () => {
    expect(formatPriceLine(null, { class: 'dollar-off', label: '$5 off', raw: '' }))
      .toBe('$5 off');
  });
  it('only original', () => {
    expect(formatPriceLine(adult30, null)).toBe('Original $30');
  });
  it('nothing useful', () => {
    expect(formatPriceLine(null, null)).toBe('');
  });
});
