import { describe, it, expect } from 'vitest';
import { haversineMiles } from './distance';

describe('haversineMiles', () => {
  it('Boston to Wakefield ~10 mi', () => {
    const d = haversineMiles({ lat: 42.3601, lon: -71.0589 }, { lat: 42.5065, lon: -71.0759 });
    expect(d).toBeGreaterThan(9);
    expect(d).toBeLessThan(13);
  });

  it('Same point ≈ 0', () => {
    const d = haversineMiles({ lat: 42, lon: -71 }, { lat: 42, lon: -71 });
    expect(d).toBeLessThan(0.001);
  });
});
