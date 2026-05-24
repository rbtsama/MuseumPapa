import { describe, it, expect } from 'vitest';
import { getLibraries, getAttractions, getAttractionBySlug, getPasses, getPassesForAttraction, getLibrary } from './load';

describe('loader', () => {
  it('59 libraries with resident_zips', () => {
    const ls = getLibraries();
    expect(ls.length).toBe(59);
    expect(getLibrary('wakefield')?.resident_zips).toContain('01880');
  });
  it('96 attractions, lookup by slug', () => {
    expect(getAttractions().length).toBeGreaterThanOrEqual(90);
    expect(getAttractionBySlug('mfa')?.name).toMatch(/Fine Arts/i);
  });
  it('passes join to attractions (no orphans)', () => {
    const slugs = new Set(getAttractions().map(a => a.slug));
    const orphan = getPasses().filter(p => !slugs.has(p.attraction_slug));
    expect(orphan.length).toBe(0);
  });
  it('passesForAttraction returns rows', () => {
    expect(getPassesForAttraction('mfa').length).toBeGreaterThan(0);
  });
});
