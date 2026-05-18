import { describe, it, expect } from 'vitest';
import { next7Days } from './dateRange';

describe('next7Days', () => {
  it('returns 7 ISO date strings starting at the given date', () => {
    const out = next7Days('2026-05-18');
    expect(out).toEqual([
      '2026-05-18', '2026-05-19', '2026-05-20', '2026-05-21',
      '2026-05-22', '2026-05-23', '2026-05-24',
    ]);
  });

  it('handles month rollover', () => {
    const out = next7Days('2026-05-28');
    expect(out).toEqual([
      '2026-05-28', '2026-05-29', '2026-05-30', '2026-05-31',
      '2026-06-01', '2026-06-02', '2026-06-03',
    ]);
  });

  it('handles year rollover', () => {
    const out = next7Days('2026-12-29');
    expect(out.slice(0, 4)).toEqual([
      '2026-12-29', '2026-12-30', '2026-12-31', '2027-01-01',
    ]);
  });
});
