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
    case 'free':         return { capacity: { kind: 'people', n: 4 }, audience_policies: [ap('free')] };
    case 'half':         return { capacity: { kind: 'people', n: 4 }, audience_policies: [ap('percent-off', 50)] };
    case 'percent-low':  return { capacity: { kind: 'people', n: 4 }, audience_policies: [ap('percent-off', 30)] };
    case 'dollar-off':   return { capacity: { kind: 'people', n: 4 }, audience_policies: [ap('dollar-off', 5)] };
    case 'per-person':   return { capacity: { kind: 'people', n: 4 }, audience_policies: [ap('per-person-price', 9)] };
    case 'discount':     return { capacity: { kind: 'people', n: 4 }, audience_policies: [ap('discount')] };
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
  // Three libraries at known distances from `userZip` so tests can rely on
  // a deterministic distance ordering (wak ≈ 0, rea ≈ 2.3 mi, bpl ≈ 9.7 mi).
  const wak = lib('wakefield', { lat: 42.5, lon: -71.07 });
  const rea = lib('reading', { lat: 42.52, lon: -71.10 });
  const bpl = lib('bpl', { lat: 42.36, lon: -71.07 });
  const wil = lib('wilmington', { lat: 42.55, lon: -71.17 });

  const userZip = { lat: 42.5, lon: -71.07 };
  // userCardLibIds containing every library so nothing gets filtered out
  // unless a test specifically wants that.
  const everyCard = new Set(['wakefield', 'reading', 'bpl', 'wilmington']);

  it('returns at most 3 entries total, with per-type caps (1 digital, 3 each physical)', () => {
    // 2 digital → only 1 should survive the per-type cap; 5 pickup → 3 survive;
    // 4 borrow → 3 survive. Overall final cap of 3 then trims by distance.
    const passes = [
      pass('bpl', 'digital', 'free'),
      pass('wilmington', 'digital', 'free'),
      pass('wakefield', 'physical-coupon', 'half'),
      pass('reading', 'physical-coupon', 'half'),
      pass('bpl', 'physical-coupon', 'half'),
      pass('wilmington', 'physical-coupon', 'half'),
      pass('wakefield', 'physical-circ', 'free'),
      pass('reading', 'physical-circ', 'free'),
      pass('bpl', 'physical-circ', 'free'),
    ];
    const out = pickTags({
      passes, libraries: [wak, rea, bpl, wil], userCardLibIds: everyCard,
      date: '2026-05-16', userGeo: userZip,
    });
    expect(out.length).toBe(3);
    // All three should be closer than wil/bpl (wakefield + reading distance is small).
    // Distances ascend.
    for (let i = 1; i < out.length; i++) {
      expect(out[i].distanceMi).toBeGreaterThanOrEqual(out[i - 1].distanceMi ?? Infinity);
    }
  });

  it('within each pass_type, sort is by distance — no coupon-rank preference', () => {
    // wakefield (close) has a weaker discount; reading (further) has FREE.
    // New rule: distance wins. Wakefield must come first.
    const passes = [
      pass('reading', 'physical-coupon', 'free'),
      pass('wakefield', 'physical-coupon', 'percent-low'),
    ];
    const out = pickTags({
      passes, libraries: [wak, rea], userCardLibIds: everyCard,
      date: '2026-05-16', userGeo: userZip,
    });
    expect(out[0].pass.library_id).toBe('wakefield');
  });

  it('drops no-card passes entirely', () => {
    const passes = [
      pass('bpl', 'digital', 'free'),
      pass('wakefield', 'physical-coupon', 'half'),
    ];
    // User only has the BPL card — wakefield should be filtered out.
    const out = pickTags({
      passes, libraries: [wak, bpl], userCardLibIds: new Set(['bpl']),
      date: '2026-05-16', userGeo: null,
    });
    expect(out.length).toBe(1);
    expect(out[0].pass.library_id).toBe('bpl');
    expect(out[0].userHasCard).toBe(true);
  });

  it('only one digital tag even when multiple digital passes exist', () => {
    const passes = [
      pass('bpl', 'digital', 'free'),
      pass('wakefield', 'digital', 'half'),
      pass('reading', 'digital', 'half'),
    ];
    const out = pickTags({
      passes, libraries: [bpl, wak, rea], userCardLibIds: everyCard,
      date: '2026-05-16', userGeo: userZip,
    });
    const digital = out.filter(o => o.pass.pass_type === 'digital');
    expect(digital.length).toBe(1);
    // Closest digital should win — wakefield is at the userZip itself.
    expect(digital[0].pass.library_id).toBe('wakefield');
  });

  it('filters out passes whose calendar marks date booked', () => {
    const passes = [
      pass('bpl', 'digital', 'free', { '2026-05-16': 'booked' }),
      pass('wakefield', 'physical-coupon', 'half', { '2026-05-16': 'available' }),
    ];
    const out = pickTags({
      passes, libraries: [wak, bpl], userCardLibIds: everyCard,
      date: '2026-05-16', userGeo: null,
    });
    expect(out.length).toBe(1);
    expect(out[0].pass.library_id).toBe('wakefield');
  });

  it('caps at maxTags (default 3, overridable)', () => {
    const passes = Array.from({ length: 10 }, (_, i) =>
      pass(`lib${i}`, 'physical-coupon', 'half'));
    const libs = Array.from({ length: 10 }, (_, i) => lib(`lib${i}`));
    const userCards = new Set(libs.map(l => l.id));
    const out = pickTags({
      passes, libraries: libs, userCardLibIds: userCards,
      date: '2026-05-16', userGeo: null,
    });
    // Per-type cap is 3 for physical-coupon, and overall cap defaults to 3
    expect(out.length).toBe(3);
  });

  it('no candidates returns []', () => {
    const out = pickTags({
      passes: [], libraries: [], userCardLibIds: null,
      date: '2026-05-16', userGeo: null,
    });
    expect(out).toEqual([]);
  });
});
