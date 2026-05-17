import { describe, it, expect } from 'vitest';
import { pickTags } from './tag-algorithm';
import type { Pass, Library, Geo, Coupon, CouponForm, AudiencePolicy } from '../data/types';

const lib = (id: string, geo: Geo | null = null): Library => ({
  id, name: id, town: id, network: 'X', platform: 'assabet',
  card_page: '', eligibility: 'open_ma_resident', supports_availability: true,
  address: null, geo,
});

type RankTier = 'free' | 'half' | 'percent-low' | 'dollar-off' | 'per-person' | 'discount';

const couponFor = (tier: RankTier): Coupon => {
  const ap = (form: CouponForm, value: number | null = null): AudiencePolicy =>
    ({ audience: 'Everyone', age_range: null, count: null, form, value });
  switch (tier) {
    case 'free':         return { capacity: { kind: 'people', n: 4 }, audience_policies: [ap('free')],                       summary: 'Up to 4 · FREE' };
    case 'half':         return { capacity: { kind: 'people', n: 4 }, audience_policies: [ap('percent-off', 50)],             summary: 'Up to 4 · 50% off' };
    case 'percent-low':  return { capacity: { kind: 'people', n: 4 }, audience_policies: [ap('percent-off', 30)],             summary: 'Up to 4 · 30% off' };
    case 'dollar-off':   return { capacity: { kind: 'people', n: 4 }, audience_policies: [ap('dollar-off', 5)],               summary: 'Up to 4 · $5 off' };
    case 'per-person':   return { capacity: { kind: 'people', n: 4 }, audience_policies: [ap('per-person-price', 9)],         summary: 'Up to 4 · $9/person' };
    case 'discount':     return { capacity: { kind: 'people', n: 4 }, audience_policies: [ap('discount')],                    summary: 'Up to 4 · Special offer' };
  }
};

const pass = (
  library_id: string,
  pass_type: Pass['pass_type'],
  tier: RankTier,
  availability: Pass['availability'] = null,
): Pass => ({
  library_id, attraction_slug: 'mos', pass_type, pass_type_raw: '',
  pickup_method: pass_type === 'digital' ? 'digital' : 'physical_at_branch',
  pickup_branches: pass_type === 'digital' ? [] : [`${library_id}--main`],
  coupon: couponFor(tier),
  restrictions: null,
  source_url: '', availability,
});

describe('pickTags', () => {
  const wak = lib('wakefield', { lat: 42.5, lon: -71.07 });
  const rea = lib('reading', { lat: 42.52, lon: -71.10 });
  const bpl = lib('bpl', { lat: 42.36, lon: -71.07 });
  const wil = lib('wilmington', { lat: 42.55, lon: -71.17 });

  const userZip = { lat: 42.5, lon: -71.07 };

  it('digital free wins slot 1; other groups fill rest', () => {
    const passes = [
      pass('bpl', 'digital', 'free'),
      pass('wakefield', 'physical-coupon', 'half'),
      pass('reading', 'physical-coupon', 'dollar-off'),
      pass('wilmington', 'physical-circ', 'free'),
    ];
    const out = pickTags({
      passes, libraries: [wak, rea, bpl, wil], userCardLibIds: null,
      date: '2026-05-16', userGeo: userZip,
    });
    expect(out.length).toBe(4);
    expect(out[0].pass.library_id).toBe('bpl');
    expect(out[0].pass.pass_type).toBe('digital');
    expect(out[1].pass.pass_type).toBe('physical-coupon');
    expect(out[1].pass.coupon.audience_policies[0].form).toBe('percent-off');
    expect(out[2].pass.pass_type).toBe('physical-coupon');
    expect(out[3].pass.pass_type).toBe('physical-circ');
  });

  it('only one digital tag even when multiple digital passes exist', () => {
    const passes = [
      pass('bpl', 'digital', 'free'),
      pass('somerville', 'digital', 'half'),
      pass('cambridge', 'digital', 'half'),
    ];
    const out = pickTags({
      passes, libraries: [bpl, lib('somerville'), lib('cambridge')], userCardLibIds: null,
      date: '2026-05-16', userGeo: null,
    });
    expect(out.length).toBe(1);
    expect(out[0].pass.coupon.audience_policies[0].form).toBe('free');
  });

  it('physical group: discount tier first, then distance', () => {
    const passes = [
      pass('reading', 'physical-coupon', 'half'),
      pass('wakefield', 'physical-coupon', 'half'),
    ];
    const out = pickTags({
      passes, libraries: [wak, rea], userCardLibIds: null,
      date: '2026-05-16', userGeo: userZip,
    });
    expect(out[0].pass.library_id).toBe('wakefield');
  });

  it('filters by userCardLibIds', () => {
    const passes = [
      pass('bpl', 'digital', 'free'),
      pass('wakefield', 'physical-coupon', 'half'),
    ];
    const out = pickTags({
      passes, libraries: [wak, bpl], userCardLibIds: new Set(['wakefield']),
      date: '2026-05-16', userGeo: null,
    });
    expect(out.length).toBe(1);
    expect(out[0].pass.library_id).toBe('wakefield');
  });

  it('filters out passes whose calendar marks date booked', () => {
    const passes = [
      pass('bpl', 'digital', 'free', { '2026-05-16': 'booked' }),
      pass('wakefield', 'physical-coupon', 'half', { '2026-05-16': 'available' }),
    ];
    const out = pickTags({
      passes, libraries: [wak, bpl], userCardLibIds: null,
      date: '2026-05-16', userGeo: null,
    });
    expect(out.length).toBe(1);
    expect(out[0].pass.library_id).toBe('wakefield');
  });

  it('caps at maxTags', () => {
    const passes = Array.from({ length: 10 }, (_, i) =>
      pass(`lib${i}`, 'physical-coupon', 'half'));
    const libs = Array.from({ length: 10 }, (_, i) => lib(`lib${i}`));
    const out = pickTags({
      passes, libraries: libs, userCardLibIds: null,
      date: '2026-05-16', userGeo: null,
    });
    expect(out.length).toBe(4);
  });

  it('no candidates returns []', () => {
    const out = pickTags({
      passes: [], libraries: [], userCardLibIds: null,
      date: '2026-05-16', userGeo: null,
    });
    expect(out).toEqual([]);
  });
});
