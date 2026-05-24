import { describe, it, expect } from 'vitest';
import { MA_ZIPS, isMaZip, townZips } from './townZips';
describe('townZips', () => {
  it('Wakefield 01880 is a MA zip', () => { expect(isMaZip('01880')).toBe(true); });
  it('out-of-state zip is not', () => { expect(isMaZip('10001')).toBe(false); });
  it('townZips(Wakefield) -> [01880]', () => { expect(townZips('Wakefield')).toContain('01880'); });
  it('MA_ZIPS non-empty', () => { expect(MA_ZIPS.size).toBeGreaterThan(50); });
});
