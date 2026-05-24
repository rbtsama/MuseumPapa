import { describe, it, expect } from 'vitest';
import { checkL1Card, checkL3Residency, checkL4VisitorResidency, checkL8Restrictions, checkL10Availability, resolvePass } from './eligibility';
import { getLibrary as realLib, getAttractionBySlug as RA } from '../data/load';

describe('L1 card/network', () => {
  it('holding the issuing library card passes', () => {
    const lib = realLib('reading')!;
    expect(checkL1Card(lib, ['reading']).ok).toBe(true);
  });
  it('holding a same-network sibling card passes', () => {
    const lib = realLib('reading')!; // NOBLE
    expect(checkL1Card(lib, ['wakefield']).ok).toBe(true); // wakefield NOBLE
  });
  it('holding only a different-network card fails', () => {
    const lib = realLib('reading')!; // NOBLE
    expect(checkL1Card(lib, ['somerville']).ok).toBe(false); // Minuteman
  });
});

describe('L3 residency (pass pickup)', () => {
  const lib = realLib('wakefield')!; // resident_zips ['01880']
  it('town-restricted pass: home zip in town -> ok', () => {
    const r = checkL3Residency({ restricted: 'yes', scope: 'town', source: null, evidence: null }, lib, '01880');
    expect(r.ok).toBe(true);
  });
  it('town-restricted pass: home zip elsewhere -> blocked', () => {
    const r = checkL3Residency({ restricted: 'yes', scope: 'town', source: null, evidence: null }, lib, '02139');
    expect(r.ok).toBe(false);
  });
  it('ma-scope: any MA zip ok', () => {
    const r = checkL3Residency({ restricted: 'yes', scope: 'ma', source: null, evidence: null }, lib, '02139');
    expect(r.ok).toBe(true);
  });
  it('open pass -> ok', () => {
    expect(checkL3Residency({ restricted: 'no', scope: null, source: null, evidence: null }, lib, '99999').ok).toBe(true);
  });
  it('unknown -> ok but warn', () => {
    const r = checkL3Residency({ restricted: 'unknown', scope: null, source: null, evidence: null }, lib, '99999');
    expect(r.ok).toBe(true); expect(r.warn).toBe(true);
  });
  it('restricted but empty home zip -> ok+warn (do not block; residency unknown)', () => {
    const town = checkL3Residency({ restricted: 'yes', scope: 'town', source: null, evidence: null }, lib, '');
    expect(town).toMatchObject({ ok: true, warn: true });
    expect(town.reason).toMatch(/home ZIP/i);
    const ma = checkL3Residency({ restricted: 'yes', scope: 'ma', source: null, evidence: null }, lib, '');
    expect(ma).toMatchObject({ ok: true, warn: true });
  });
});

describe('L4 attraction visitor residency', () => {
  it('no rule -> ok', () => { expect(checkL4VisitorResidency(null, '99999').ok).toBe(true); });
  it('residency none -> ok', () => { expect(checkL4VisitorResidency({ residency:'none' }, '99999').ok).toBe(true); });
  it('ma_resident: MA zip ok, non-MA blocked', () => {
    expect(checkL4VisitorResidency({ residency:'ma_resident' }, '01880').ok).toBe(true);
    expect(checkL4VisitorResidency({ residency:'ma_resident' }, '10001').ok).toBe(false);
  });
  it('unknown -> ok+warn', () => {
    expect(checkL4VisitorResidency({ residency:'unknown' }, '10001')).toMatchObject({ ok:true, warn:true });
  });
  it('ma_resident with empty home zip -> ok+warn (do not block)', () => {
    expect(checkL4VisitorResidency({ residency:'ma_resident' }, '')).toMatchObject({ ok:true, warn:true });
  });
});

describe('time layers', () => {
  it('blackout month/day on target date blocks (L8)', () => {
    const r = checkL8Restrictions({ blackout:[{month:7,day:4}], blackout_recurring:[], weekdays_only:false, seasonal:null, advance_booking_required:false, advance_booking_hours:null }, new Date('2026-07-04'));
    expect(r.ok).toBe(false);
  });
  it('weekdays_only blocks weekend (L8)', () => {
    const r = checkL8Restrictions({ blackout:[], blackout_recurring:[], weekdays_only:true, seasonal:null, advance_booking_required:false, advance_booking_hours:null }, new Date('2026-06-06')); // Saturday
    expect(r.ok).toBe(false);
  });
  it('availability available -> ok, booked -> blocked (L10)', () => {
    expect(checkL10Availability({ '2026-06-01':'available' }, '2026-06-01').ok).toBe(true);
    expect(checkL10Availability({ '2026-06-01':'booked' }, '2026-06-01').ok).toBe(false);
  });
  it('availability missing date -> unknown warn (L10)', () => {
    expect(checkL10Availability({}, '2026-06-01')).toMatchObject({ ok:true, warn:true });
  });
});

describe('resolvePass', () => {
  it('wakefield resident-only pass: Wakefield home ok, other-zip blocked at L3', () => {
    const lib = realLib('wakefield')!; const attr = RA('mfa')!;
    const pass = { library_id:'wakefield', attraction_slug:'mfa', pass_form:'physical_coupon' as const, available_at_branches:'all' as const, coupon:null, restrictions:null, residency_restriction:{restricted:'yes' as const, scope:'town' as const, source:null, evidence:null}, availability:{} };
    const home = resolvePass(pass, lib, attr, { homeZip:'01880', heldLibraryIds:['wakefield'] });
    expect(home.eligible).toBe(true);
    const away = resolvePass(pass, lib, attr, { homeZip:'02139', heldLibraryIds:['wakefield'] });
    expect(away.eligible).toBe(false);
    expect(away.blockedLayer).toBe('L3');
  });

  it('reads the SAME ISO date that the page passes in — no off-by-one (FIX 2)', () => {
    // Sanity: parsing a YYYY-MM-DD string yields UTC midnight, so toISOString
    // round-trips to the same day (the construction the list + detail pages use).
    expect(new Date('2026-05-25').toISOString().slice(0, 10)).toBe('2026-05-25');

    const lib = realLib('wakefield')!; const attr = RA('mfa')!;
    // Availability map: target day available, neighbor days booked.
    const pass = {
      library_id:'wakefield', attraction_slug:'mfa', pass_form:'physical_coupon' as const,
      available_at_branches:'all' as const, coupon:null, restrictions:null,
      residency_restriction:{restricted:'no' as const, scope:null, source:null, evidence:null},
      availability:{ '2026-05-24':'booked', '2026-05-25':'available', '2026-05-26':'booked' },
    };
    const user = { homeZip:'01880', heldLibraryIds:['wakefield'] };
    // Picking 2026-05-25 must read THAT day's 'available', not a neighbor's 'booked'.
    const v = resolvePass(pass, lib, attr, user, new Date('2026-05-25'));
    expect(v.eligible).toBe(true);
    // Picking a booked day must block at L10.
    const booked = resolvePass(pass, lib, attr, user, new Date('2026-05-26'));
    expect(booked.eligible).toBe(false);
    expect(booked.blockedLayer).toBe('L10');
  });
});
