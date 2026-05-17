import { describe, it, expect } from 'vitest';
import {
  getLibraries, getAttractions, getAttractionBySlug,
  getPasses, getPassesForAttraction,
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

  it('looks up attraction by slug', () => {
    const mos = getAttractionBySlug('museum-of-science');
    expect(mos).toBeDefined();
    expect(mos!.museum_name.toLowerCase()).toContain('museum of science');
  });

  it('filters passes by attraction slug', () => {
    const mosPasses = getPassesForAttraction('museum-of-science');
    expect(mosPasses.length).toBeGreaterThan(0);
  });
});
