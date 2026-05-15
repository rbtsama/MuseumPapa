import { describe, it, expect } from 'vitest';
import { pickTags } from './tag-algorithm';
import type { Pass, Library, Geo } from '../data/types';

const lib = (id: string, geo: Geo | null = null): Library => ({
  id, name: id, town: id, network: 'X', platform: 'assabet',
  card_page: '', eligibility: 'open_ma_resident', supports_availability: true,
  address: null, geo,
});

const pass = (
  library_id: string,
  pass_type: Pass['pass_type'],
  discountClass: Pass['discount']['class'],
  label: string,
  availability: Pass['availability'] = null,
): Pass => ({
  library_id, attraction_slug: 'mos', pass_type, pass_type_raw: '',
  discount: { class: discountClass, label, raw: '' },
  source_url: '', availability,
});

describe('pickTags', () => {
  const wak = lib('wakefield', { lat: 42.5, lon: -71.07 });
  const rea = lib('reading', { lat: 42.52, lon: -71.10 });
  const bpl = lib('bpl', { lat: 42.36, lon: -71.07 });
  const wil = lib('wilmington', { lat: 42.55, lon: -71.17 });

  const userZip = { lat: 42.5, lon: -71.07 };  // pretend Wakefield ZIP

  it('digital free wins slot 1; other groups fill rest', () => {
    const passes = [
      pass('bpl', 'digital', 'free', 'Free'),
      pass('wakefield', 'physical-coupon', 'half', '50% off'),
      pass('reading', 'physical-coupon', 'dollar-off', '$5 off'),
      pass('wilmington', 'loan-card', 'free', 'Free'),
    ];
    const out = pickTags({
      passes, libraries: [wak, rea, bpl, wil], userCardLibIds: null,
      date: '2026-05-16', userGeo: userZip,
    });
    expect(out.length).toBe(4);
    expect(out[0].pass.library_id).toBe('bpl');
    expect(out[0].pass.pass_type).toBe('digital');
    expect(out[1].pass.pass_type).toBe('physical-coupon');
    expect(out[1].pass.discount.class).toBe('half');  // higher rank than dollar-off
    expect(out[2].pass.pass_type).toBe('physical-coupon');
    expect(out[3].pass.pass_type).toBe('loan-card');
  });

  it('only one digital tag even when multiple digital passes exist', () => {
    const passes = [
      pass('bpl', 'digital', 'free', 'Free'),
      pass('somerville', 'digital', 'half', '50% off'),
      pass('cambridge', 'digital', 'half', '50% off'),
    ];
    const out = pickTags({
      passes, libraries: [bpl, lib('somerville'), lib('cambridge')], userCardLibIds: null,
      date: '2026-05-16', userGeo: null,
    });
    expect(out.length).toBe(1);
    expect(out[0].pass.discount.class).toBe('free');  // free beats half
  });

  it('physical group: discount tier first, then distance', () => {
    const passes = [
      pass('reading', 'physical-coupon', 'half', '50% off'),
      pass('wakefield', 'physical-coupon', 'half', '50% off'),
    ];
    const out = pickTags({
      passes, libraries: [wak, rea], userCardLibIds: null,
      date: '2026-05-16', userGeo: userZip,
    });
    // Both half-price, but wakefield is closer
    expect(out[0].pass.library_id).toBe('wakefield');
  });

  it('filters by userCardLibIds', () => {
    const passes = [
      pass('bpl', 'digital', 'free', 'Free'),
      pass('wakefield', 'physical-coupon', 'half', '50% off'),
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
      pass('bpl', 'digital', 'free', 'Free', { '2026-05-16': 'booked' }),
      pass('wakefield', 'physical-coupon', 'half', '50% off', { '2026-05-16': 'available' }),
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
      pass(`lib${i}`, 'physical-coupon', 'half', '50% off'));
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
