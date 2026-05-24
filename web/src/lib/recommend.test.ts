import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { Library, Attraction, Pass, Coupon } from '../data/types';

// Mock the data layer so recommend() runs against deterministic fixtures.
const passesByAttr: Record<string, Pass[]> = {};
const libsById: Record<string, Library> = {};
const attrsBySlug: Record<string, Attraction> = {};

vi.mock('../data/load', () => ({
  getPassesForAttraction: (slug: string) => passesByAttr[slug] ?? [],
  getLibrary: (id: string) => libsById[id],
  getAttractionBySlug: (slug: string) => attrsBySlug[slug],
}));

import { recommend } from './recommend';

function lib(id: string, network: string): Library {
  return {
    id, name: `${id} Library`, town: id, network, platform: network,
    card_page: null, address: null, geo: null,
    card_eligibility: 'none', pass_pickup_default: 'none', resident_zips: [],
  };
}

const freeCoupon: Coupon = {
  capacity: { kind: 'people', n: 4 },
  audience_policies: [{ audience: 'Everyone', form: 'free', value: null }],
};
const discountCoupon: Coupon = {
  capacity: { kind: 'people', n: 4 },
  audience_policies: [{ audience: 'Everyone', form: 'percent-off', value: 50 }],
};

function pass(libId: string, form: Pass['pass_form'], coupon: Coupon, over: Partial<Pass> = {}): Pass {
  return {
    library_id: libId, attraction_slug: 'zoo', pass_form: form,
    available_at_branches: 'all', coupon,
    restrictions: null, residency_restriction: { restricted: 'no', scope: null },
    availability: {}, ...over,
  };
}

const ATTR: Attraction = {
  slug: 'zoo', name: 'Zoo', categories: [], prices: [], sources: [],
  visitor_eligibility: null, reservation: null,
};

beforeEach(() => {
  for (const k of Object.keys(passesByAttr)) delete passesByAttr[k];
  for (const k of Object.keys(libsById)) delete libsById[k];
  for (const k of Object.keys(attrsBySlug)) delete attrsBySlug[k];
  attrsBySlug.zoo = ATTR;
});

describe('recommend', () => {
  it('returns at most 4 and dedups eligible email passes to 1', () => {
    libsById.held = lib('held', 'noble');
    // Two email passes (both eligible — same network card held) + physical passes.
    passesByAttr.zoo = [
      pass('held', 'digital_email', freeCoupon),
      pass('held', 'digital_email', discountCoupon),
      pass('held', 'physical_coupon', discountCoupon),
      pass('held', 'physical_circ', discountCoupon),
      pass('held', 'physical_coupon', freeCoupon),
    ];
    const recs = recommend('zoo', { homeZip: '01880', heldLibraryIds: ['held'] });
    expect(recs.length).toBeLessThanOrEqual(4);
    const emails = recs.filter(r => r.pass.pass_form === 'digital_email');
    expect(emails.length).toBe(1);
    // The kept email must be the eligible one.
    expect(emails[0].verdict.eligible).toBe(true);
  });

  it('does NOT force an INELIGIBLE email pass above eligible passes (FIX 5)', () => {
    // Email pass is from a library whose network the user does NOT hold → L1 ineligible.
    // Physical pass is from a held library → eligible.
    libsById.held = lib('held', 'noble');
    libsById.other = lib('other', 'minuteman');
    passesByAttr.zoo = [
      pass('other', 'digital_email', freeCoupon),     // ineligible (no minuteman card)
      pass('held', 'physical_coupon', discountCoupon), // eligible
    ];
    const recs = recommend('zoo', { homeZip: '01880', heldLibraryIds: ['held'] });
    // The lead rec must be eligible (the physical pass), not the ineligible email.
    expect(recs[0].verdict.eligible).toBe(true);
    expect(recs[0].pass.pass_form).toBe('physical_coupon');
    // The ineligible email may still appear, but never above an eligible pass.
    const emailIdx = recs.findIndex(r => r.pass.pass_form === 'digital_email');
    if (emailIdx >= 0) {
      expect(recs[emailIdx].verdict.eligible).toBe(false);
      expect(emailIdx).toBeGreaterThan(0);
    }
  });

  it('forces an ELIGIBLE email pass to the top', () => {
    libsById.held = lib('held', 'noble');
    passesByAttr.zoo = [
      pass('held', 'physical_coupon', freeCoupon),     // eligible, strong coupon
      pass('held', 'digital_email', discountCoupon),   // eligible, weaker coupon
    ];
    const recs = recommend('zoo', { homeZip: '01880', heldLibraryIds: ['held'] });
    // Eligible email is prepended to the top even though its coupon is weaker.
    expect(recs[0].pass.pass_form).toBe('digital_email');
    expect(recs[0].verdict.eligible).toBe(true);
  });
});
