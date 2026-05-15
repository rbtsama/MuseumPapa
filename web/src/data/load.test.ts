import { describe, it, expect } from 'vitest';
import {
  getLibraries, getLibraryById, getAttractions, getAttractionBySlug,
  getPasses, getPassesForAttraction, getPassesForLibrary,
} from './load';

describe('data loader', () => {
  it('loads >=40 libraries', () => {
    expect(getLibraries().length).toBeGreaterThanOrEqual(40);
  });

  it('loads >=80 attractions', () => {
    expect(getAttractions().length).toBeGreaterThanOrEqual(80);
  });

  it('loads >=500 passes', () => {
    expect(getPasses().length).toBeGreaterThanOrEqual(500);
  });

  it('looks up library by id', () => {
    const w = getLibraryById('wakefield');
    expect(w).toBeDefined();
    expect(w!.town).toBe('Wakefield');
  });

  it('looks up attraction by slug', () => {
    const mos = getAttractionBySlug('museum-of-science');
    expect(mos).toBeDefined();
    expect(mos!.museum_name.toLowerCase()).toContain('museum of science');
  });

  it('filters passes by attraction slug', () => {
    const mosPasses = getPassesForAttraction('museum-of-science');
    expect(mosPasses.length).toBeGreaterThan(0);
  });

  it('filters passes by library id', () => {
    const wakPasses = getPassesForLibrary('wakefield');
    expect(wakPasses.length).toBeGreaterThan(0);
  });
});
