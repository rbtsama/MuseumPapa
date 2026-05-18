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

  it('delivery-cost order: Email first, then Pickup, then Borrow', () => {
    // Closest pass is a Borrow at the user's ZIP; furthest is a Pickup. Old
    // distance-only sort would put Borrow first. New rule puts Email first,
    // then any Pickup (no matter how far), then Borrow last.
    const passes = [
      pass('bpl', 'digital', 'half'),                  // far Email
      pass('reading', 'physical-coupon', 'percent-low'), // far Pickup
      pass('wakefield', 'physical-circ', 'free'),      // closest Borrow
    ];
    const out = pickTags({
      passes, libraries: [wak, rea, bpl], userCardLibIds: everyCard,
      date: '2026-05-16', userGeo: userZip,
    });
    expect(out.length).toBe(3);
    expect(out[0].pass.pass_type).toBe('digital');         // Email
    expect(out[1].pass.pass_type).toBe('physical-coupon'); // Pickup
    expect(out[2].pass.pass_type).toBe('physical-circ');   // Borrow
  });

  it('within a pass_type, distance asc, then coupon strength as tiebreaker', () => {
    // Two Pickups at the same distance (same library). The stronger discount
    // (FREE) should win the tiebreaker over the weaker one (per-person).
    const passes = [
      pass('wakefield', 'physical-coupon', 'per-person'),
      pass('wakefield', 'physical-coupon', 'free'),
    ];
    const out = pickTags({
      passes, libraries: [wak], userCardLibIds: everyCard,
      date: '2026-05-16', userGeo: userZip,
    });
    expect(out[0].pass.coupon.audience_policies[0].form).toBe('free');
  });

  it('per-type cap holds: 1 Email + 3 Pickup + 3 Borrow candidate pool, sliced to 3 total', () => {
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
    // Delivery-cost order: Email block first, then Pickup block. Borrow never
    // surfaces here since Pickup already filled the remaining 2 slots.
    expect(out[0].pass.pass_type).toBe('digital');
    expect(out[1].pass.pass_type).toBe('physical-coupon');
    expect(out[2].pass.pass_type).toBe('physical-coupon');
    // Pickups within the block are ordered by distance asc.
    expect(out[1].distanceMi).toBeLessThanOrEqual(out[2].distanceMi ?? Infinity);
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
