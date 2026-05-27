import { describe, it, expect } from 'vitest';
import { MA_ZIPS, isMaZip, townZips } from './townZips';
describe('townZips', () => {
  it('Wakefield 01880 is a MA zip', () => { expect(isMaZip('01880')).toBe(true); });
  it('a real MA zip outside our seed towns counts (01886 Westford)', () => { expect(isMaZip('01886')).toBe(true); });
  it('western MA (01001) and Cape (02601) count', () => { expect(isMaZip('01001')).toBe(true); expect(isMaZip('02601')).toBe(true); });
  it('out-of-state zip is not', () => { expect(isMaZip('10001')).toBe(false); });
  it('neighboring RI (02860) and NH (03801) are not MA', () => { expect(isMaZip('02860')).toBe(false); expect(isMaZip('03801')).toBe(false); });
  it('empty / malformed zip is not MA', () => { expect(isMaZip('')).toBe(false); expect(isMaZip('123')).toBe(false); });
  it('townZips(Wakefield) -> [01880]', () => { expect(townZips('Wakefield')).toContain('01880'); });
  it('MA_ZIPS non-empty', () => { expect(MA_ZIPS.size).toBeGreaterThan(50); });
});
