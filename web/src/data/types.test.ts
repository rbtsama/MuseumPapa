import { describe, it, expect } from 'vitest';
import type { Library, Attraction, Pass } from './types';

describe('types match structured json', () => {
  it('Library has resident_zips + card_eligibility + pass_pickup_default', () => {
    const l: Library = {
      id: 'wakefield', name: 'X', town: 'Wakefield', network: 'NOBLE',
      platform: 'assabet', card_page: 'http://x', address: null, geo: null,
      card_eligibility: 'ma_resident', pass_pickup_default: 'unknown',
      resident_zips: ['01880'],
    };
    expect(l.resident_zips[0]).toBe('01880');
  });
  it('Pass has residency_restriction + pass_form + availability map', () => {
    const p: Pass = {
      library_id: 'wakefield', attraction_slug: 'mfa', pass_form: 'digital_email',
      available_at_branches: 'all', coupon: null, restrictions: null,
      residency_restriction: { restricted: 'yes', scope: 'town', source: null, evidence: null },
      availability: { '2026-06-01': 'available' },
    };
    expect(p.residency_restriction.restricted).toBe('yes');
    expect(p.availability['2026-06-01']).toBe('available');
  });
});
