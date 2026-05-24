import { describe, it, expect } from 'vitest';
import { checkL1Card, checkL3Residency, checkL4VisitorResidency } from './eligibility';
import { getLibrary as realLib } from '../data/load';

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
});
